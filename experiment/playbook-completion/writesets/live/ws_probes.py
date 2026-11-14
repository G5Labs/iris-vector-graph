#!/usr/bin/env python3
"""Writesets lane: live probes for the writer-census obligations, namespace AUDITB, through the pin's own entry points.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1200 \
        python experiment/playbook-completion/writesets/live/ws_probes.py <case> [<case> ...]

Cases (each writes $RUN_DIR/writesets/<case>.json and starts and ends with Eraser.EraseAll + Ledger.PurgeAll):

  ins-<writer>   A ledger-bypassing writer that inserts node (or property) rows, against INV-replay, INV-marker and
                 INV-no-live-tombstone. (1) replay: verify() before and after the writer writes a fresh entity of a
                 control prefix, with the journal (traces/journal.py) as oracle of what the writer's process wrote;
                 (2) interleave: the target tenant is erased, a redaction of it is started on connection A while
                 connection B holds the ledger head lock (as a concurrent ledger commit does), so the run passes its
                 entry liveness check and waits for the lock; the writer, on connection W, writes the target's
                 content; B releases. The journal gives the order of W's content writes and A's tombstones; then the
                 marker, verify(), a ledger commit into the target and a re-run are observed.
  fk-guard       The composite foreign keys that stop an edge or label row from making a non-live target live.
  rb-delete_reification
                 F-C1301 with a real bypass deleter: delete_reification inside a caller transaction (WriteTxn nests
                 in it, _write_txn.py), a redaction on another connection while the delete is uncommitted, then the
                 caller's rollback.
  stmt-collision A ledger relationship whose qualifiers carry the temporal or inferred marker key, then the writers
                 that delete marked rows (TemporalIndex.DeleteTemporalEdge -> Adjacency.RetractTemporalRow,
                 TemporalPolicy.DropRows, retract_inference): INV-stmt (live statement without its row).
  stmt-purge     INV-stmt for RetractTemporalRows (the purge path) with a marker-key qualifier.
  migrations     ensure_indexes' migrations while a redaction marker exists, and add_graph_id_to_nodes.
  replay-delete_reification, replay-import_rdf
                 INV-replay sub-checks re-run alone (review R4-02, R4-06): committed delete; equal baseline.
  noindex-erase  The %NOINDEX edge row of BulkLoader.load_edges against delete_nodes_by_prefix and EraseAll+PurgeAll.
  noindex        BulkLoader.load_nodes' %NOINDEX rows against LiveRows (outside the census cells).
  fhir-blocked   Graph.KG.FHIRGraph.Register here (no FHIR repository: the FHIR writers are not runnable).
  snap-helpers   Graph.KG.Snapshot.ImportGlobals over the ledger global (and SetNodeJSON's refusal of it).
  snap-setnodejson  Graph.KG.Snapshot.SetNodeJSON's allow-list against every store the 8 invariants read (guard).
  sql-guard      sql-insert without the INSERT of the next seq (the INV-text guard alone).
  sql-insert     The SQL surface of Graph_KG.ledger_revisions against INV-text (unique seq, triggers), and an INSERT
                 of the next seq followed by a ledger commit.
  gap-marker     WS-GAP-001: a marker of the live ledger and a replacing restore of an archive holding the target.
  gap-restore    restore_snapshot's undeclared writes of redactedRev / idemRedacted (WS-GAP-002/003): a replacing
                 restore of a pre-redaction archive, then the same tenant erased and redacted again.

Connections: at most 4 at once. Nothing is compiled, no product file is touched; scratch files only under
$RUN_DIR/writesets/ (client side) and /tmp/IVGAuditWS-* inside the container (removed at the end).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parents[1]
sys.path.insert(0, str(PC / "tools"))
sys.path.insert(0, str(PC / "traces"))
from iris_conn import Conn, version  # noqa: E402
import journal  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITB"
OUT = Path(os.environ["RUN_DIR"]) / "writesets"
OUT.mkdir(parents=True, exist_ok=True)
CONTENT = ("sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_edges")
TS = 1700000000


# ------------------------------------------------------------------------------------------------------ helpers

def eng(c: Conn) -> IRISGraphEngine:
    return IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)


def reset(c: Conn) -> None:
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.conn.commit()


def err(fn):
    try:
        r = fn()
        return {"ok": True, "value": r}
    except Exception as e:  # the outcome is data
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)[:700]}


def receipt_dict(r) -> dict:
    d = {k: getattr(r, k, None) for k in ("complete", "records_tombstoned", "metadata_cleared",
                                          "idempotency_keys_removed", "statements_removed", "batches")}
    d["redaction_seq"] = r.redaction.seq if getattr(r, "redaction", None) else None
    return d


def marker(c: Conn) -> dict:
    return json.loads(str(c.call("Graph.KG.LedgerRedact", "InProgress")))


def live_rows(c: Conn, prefix: str, graph: str | None = None) -> dict:
    """LedgerRedact.LiveRows' counts for a prefix target (LedgerRedact.cls:149-178): with graph None nodes, labels and
    properties in every graph, edges in the default graph; with a graph, everything in that graph."""
    p = prefix + "|"
    if graph is None:
        g = "COALESCE(graph_id, '') = ''"
        return {
            "nodes": c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE %EXACT(node_id) %STARTSWITH ?", p)[0][0],
            "rdf_labels": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE %EXACT(s) %STARTSWITH ?", p)[0][0],
            "rdf_props": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE %EXACT(s) %STARTSWITH ?", p)[0][0],
            "rdf_edges": c.sql(f"SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE {g} AND (%EXACT(s) %STARTSWITH ? "
                               "OR %EXACT(o_id) %STARTSWITH ?)", p, p)[0][0],
        }
    g = "graph_id = ?"
    return {t: c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE {g}", graph)[0][0]
            for t in ("nodes", "rdf_labels", "rdf_props", "rdf_edges")}


def ledger_recs(c: Conn) -> list:
    out = []
    for seq, _ in c.o.iterator("^IVG.Ledger", "rec").items():
        for o_, _ in c.o.iterator("^IVG.Ledger", "rec", seq).items():
            lst = c.o.getIRISList("^IVG.Ledger", "rec", seq, o_)
            out.append({"seq": str(seq), "ord": str(o_), "op": str(lst.get(1)), "id": str(lst.get(3) or "")})
    return out


def verify(e) -> dict:
    def go():
        v = e.ledger.verify()
        return {"result": str(v.result), "classification": getattr(v, "classification", None),
                "differences": [str(x)[:200] for x in (getattr(v, "differences", None) or [])][:6]}
    return err(go)


def jrecs(m, pids):
    return journal.records_since(m, pids={str(p) for p in pids})


def content_writes(recs, smap, pid) -> dict:
    out = {}
    for r in recs:
        if r["p"] != str(pid) or not r["g"]:
            continue
        st = journal.store_of(r["g"], smap)
        if st in CONTENT:
            out.setdefault(st, []).append(r["a"])
    return {k: {"n": len(v), "first": min(v), "last": max(v)} for k, v in out.items()}


def ledger_writes(recs, pid) -> dict:
    out = {}
    for r in recs:
        if r["p"] == str(pid) and r["g"].startswith('^IVG.Ledger('):
            key = r["g"].split(",")[0].replace("^IVG.Ledger(", "").rstrip(")")
            out[key] = out.get(key, 0) + 1
    return out


def tombstone_addrs(recs, pid) -> list:
    out = []
    for r in recs:
        if r["p"] == str(pid) and r["g"].startswith('^IVG.Ledger("rec",') and r["t"].startswith("SET") and r["n"]:
            if b"redacted" in base64.b64decode(r["n"]):
                out.append(r["a"])
    return out


def txn_end_of(recs, pid, addr):
    """Address of the CommitTrans that closes the transaction holding `addr`, or the record itself (autocommit)."""
    for u in journal.transactions([r for r in recs if r["p"] == str(pid)]):
        if addr in u.get("addresses", []):
            return {"kind": u["kind"], "committed": u["committed"], "end": u.get("end"), "rolled_back": u.get("rolled_back")}
    return None


# --------------------------------------------------------------------------------------- writers (entry points)

def _store(c: Conn):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    return IRISGraphStore(c.conn, namespace=NS)


def _rdf_file(prefix: str) -> str:
    p = OUT / f"{prefix}.ttl"
    p.write_text(f"<urn:{prefix}:n1> <urn:p:R> <urn:{prefix}:n2> .\n<urn:{prefix}:n1> <urn:p:secret> \"w\" .\n")
    return str(p)


def _ctl_edge_id(c: Conn) -> int:
    return int(c.sql("SELECT TOP 1 edge_id FROM Graph_KG.rdf_edges WHERE s = 'wsctl|n1'")[0][0])


# name -> (census writer, write(e, c, prefix), id prefix form for the target: "pipe" = "<p>|x", "urn" = "urn:<p>:x")
WRITERS = {
    "store_node": ("iris_vector_graph/_engine/nodes_edges.py::store_node",
                   lambda e, c, p: e.store_node(f"{p}|n1", {"secret": "w"}, ["W"]), "pipe"),
    "store_edge": ("iris_vector_graph/_engine/nodes_edges.py::store_edge",
                   lambda e, c, p: e.store_edge(f"{p}|n1", "R", f"{p}|n2"), "pipe"),
    "bulk_create_nodes": ("iris_src/src/Graph/KG/EdgeScan.cls::BulkIngestNodesSQL (+RegisterDefaultNode)",
                          lambda e, c, p: e.bulk_create_nodes([{"id": f"{p}|n1", "labels": ["W"],
                                                                "properties": {"secret": "w"}}]), "pipe"),
    "bulk_ingest_edges": ("iris_src/src/Graph/KG/EdgeScan.cls::BulkIngestEdgesSQL (+RegisterDefaultNode)",
                          lambda e, c, p: e.bulk_ingest_edges([(f"{p}|n1", f"{p}|n2", "R")], auto_sync=False), "pipe"),
    "bulk_create_edges": ("iris_vector_graph/_engine/nodes_edges.py::bulk_create_edges",
                          lambda e, c, p: e.bulk_create_edges([{"source_id": f"{p}|n1", "predicate": "R",
                                                                "target_id": f"{p}|n2"}], auto_sync=False), "pipe"),
    "store_write_nodes": ("iris_vector_graph/stores/iris_sql_store.py::write_nodes",
                          lambda e, c, p: _store(c).write_nodes([{"id": f"{p}|n1", "labels": ["W"],
                                                                  "properties": {"secret": "w"}}]), "pipe"),
    "store_write_edges": ("iris_vector_graph/stores/iris_sql_store.py::write_edges",
                          lambda e, c, p: _store(c).write_edges([{"source": f"{p}|n1", "predicate": "R",
                                                                  "target": f"{p}|n2"}]), "pipe"),
    "create_edge_temporal": ("iris_vector_graph/_engine/temporal.py::create_edge_temporal",
                             lambda e, c, p: e.create_edge_temporal(f"{p}|n1", "RT", f"{p}|n2", timestamp=TS), "pipe"),
    "bulk_create_edges_temporal": ("iris_vector_graph/_engine/temporal.py::bulk_create_edges_temporal",
                                   lambda e, c, p: e.bulk_create_edges_temporal(
                                       [{"s": f"{p}|n1", "p": "RT", "o": f"{p}|n2", "ts": TS}]), "pipe"),
    "reify_edge": ("iris_vector_graph/_engine/schema.py::reify_edge",
                   lambda e, c, p: e.reify_edge(_ctl_edge_id(c), reifier_id=f"{p}|r1", props={"secret": "w"}), "pipe"),
    "bulkloader_load_edges": ("iris_vector_graph/bulk_loader.py::_register_endpoints",
                              lambda e, c, p: __import__("iris_vector_graph.bulk_loader", fromlist=["BulkLoader"])
                              .BulkLoader(c.conn).load_edges([(f"{p}|n1", "R", f"{p}|n2", None)]), "pipe"),
    "import_rdf": ("iris_vector_graph/_engine/snapshot.py::import_rdf",
                   lambda e, c, p: e.import_rdf(_rdf_file(p)), "urn"),
}


def ids_of(form: str, p: str, n: str) -> str:
    return f"{p}|{n}" if form == "pipe" else f"urn:{p}:{n}"


def target_args(form: str, p: str):
    return (p, "|") if form == "pipe" else (f"urn:{p}", ":")


def live_rows_form(c: Conn, form: str, p: str) -> dict:
    if form == "pipe":
        return live_rows(c, p)
    q = f"urn:{p}:"
    return {"nodes": c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE %EXACT(node_id) %STARTSWITH ?", q)[0][0],
            "rdf_props": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE %EXACT(s) %STARTSWITH ?", q)[0][0],
            "rdf_edges": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE %EXACT(s) %STARTSWITH ? OR "
                               "%EXACT(o_id) %STARTSWITH ?", q, q)[0][0]}


def commit_form(e, form: str, p: str):
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message=f"{p} content")
    a, b = ids_of(form, p, "n1"), ids_of(form, p, "n2")
    cs.create_node(a, labels=["T"], properties={"secret": f"{p}-s1"})
    cs.create_node(b, labels=["T"], properties={"secret": f"{p}-s2"})
    cs.create_relationship(a, "R", b)
    return e.ledger.commit(cs).revision


def erase_form(e, c: Conn, form: str, p: str):
    pre, sep = target_args(form, p)
    r = e.delete_nodes_by_prefix(pre + sep)
    c.conn.commit()
    return r


# ------------------------------------------------------------------------------------------------------- cases

def case_ins(c: Conn, name: str) -> dict:
    writer, write, form = WRITERS[name]
    i = list(WRITERS).index(name)
    T, D = f"wst{i:02d}", f"wsd{i:02d}"
    reset(c)
    smap = journal.storage_map(c)
    e = eng(c)
    e.ledger.enable()
    out = {"writer": writer, "entry_point": name, "target": target_args(form, T), "control": target_args(form, D)}
    # control tenant (recorded, stays live) and the target tenant (recorded, erased later)
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="control")
    cs.create_node("wsctl|n1", labels=["C"], properties={"k": "v"}).create_node("wsctl|n2", labels=["C"])
    cs.create_relationship("wsctl|n1", "R", "wsctl|n2")
    e.ledger.commit(cs)
    out["target_revision"] = commit_form(e, form, T).seq
    out["records_of_target"] = sum(1 for r in ledger_recs(c) if T in r["id"])
    out["verify_baseline"] = verify(e)
    # (1) INV-replay: the writer on a fresh control prefix D, journal-observed
    cW = Conn(NS)
    try:
        eW = eng(cW)
        m1 = journal.mark()
        out["replay_write"] = err(lambda: str(write(eW, cW, D))[:200])
        cW.conn.commit()
        r1 = jrecs(m1, [cW.pid])
        out["replay_journal"] = {"content_writes": content_writes(r1, smap, cW.pid),
                                 "ledger_writes": ledger_writes(r1, cW.pid)}
        out["replay_live_rows_D"] = live_rows_form(c, form, D)
        out["verify_after_write"] = verify(e)
        erase_form(e, c, form, D)
        out["verify_after_erasing_D"] = verify(e)
        # (2) interleave: erase T; redaction on A passes its entry check and waits for the head lock B holds
        out["erase_target"] = err(lambda: erase_form(e, c, form, T))
        out["live_rows_after_erase"] = live_rows_form(c, form, T)
        cA, cB = Conn(NS), Conn(NS)
        try:
            eA = eng(cA)
            pre, sep = target_args(form, T)
            m2 = journal.mark()
            cB.o.lock("", 5, "^IVG.Ledger", "head")
            box = {}
            th = threading.Thread(target=lambda: box.update(
                redact=err(lambda: receipt_dict(eA.ledger.redact(None, prefix=pre, separator=sep, batch_size=100))))
            )
            th.start()
            time.sleep(2.5)
            box["redaction_waiting"] = th.is_alive()
            wbox = {}
            tw = threading.Thread(target=lambda: wbox.update(w=err(lambda: str(write(eW, cW, T))[:200])))
            tw.start()
            tw.join(25)
            box["writer_returned_while_lock_held"] = not tw.is_alive()
            box["write"] = wbox.get("w")
            if not tw.is_alive():
                cW.conn.commit()
            box["live_rows_after_write"] = live_rows_form(c, form, T)
            cB.o.unlock("", "^IVG.Ledger", "head")
            th.join(90)
            tw.join(60)
            if box.get("write") is None:
                box["write"] = wbox.get("w")
                cW.conn.commit()
            out["interleave"] = box
            r2 = jrecs(m2, [cA.pid, cW.pid])
            cw = content_writes(r2, smap, cW.pid)
            tombs = tombstone_addrs(r2, cA.pid)
            w_last = max((v["last"] for v in cw.values()), default=None)
            w_txn = txn_end_of(r2, cW.pid, w_last) if w_last else None
            out["interleave_journal"] = {
                "writer_content_writes": cw, "writer_ledger_writes": ledger_writes(r2, cW.pid),
                "writer_last_content_txn": w_txn,
                "tombstones": len(tombs), "first_tombstone": min(tombs) if tombs else None,
                "redaction_ledger_writes": ledger_writes(r2, cA.pid),
                "tombstoned_after_writer_committed": bool(tombs and w_txn and w_txn.get("committed")
                                                          and min(tombs) > (w_txn.get("end") or w_last)),
            }
        finally:
            cA.close()
            cB.close()
        out["marker_after"] = marker(c)
        out["live_rows_after_run"] = live_rows_form(c, form, T)
        out["tombstones_now"] = sum(1 for r in ledger_recs(c) if r["op"] == "redacted")
        out["verify_after_run"] = verify(e)
        out["ledger_commit_into_target"] = err(lambda: e.ledger.commit(
            Changeset(actor="audit:writesets", actor_type="ingest").create_node(ids_of(form, T, "via"))).revision.seq)
        out["rerun"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix=pre, separator=sep)))
        out["marker_after_rerun"] = marker(c)
    finally:
        cW.close()
    reset(c)
    il, ij = out.get("interleave", {}), out.get("interleave_journal", {})
    out["verdict"] = {
        "replay_writer_wrote_content": bool(out["replay_journal"]["content_writes"]),
        "replay_writer_wrote_no_ledger_record": "\"rec\"" not in out["replay_journal"]["ledger_writes"],
        "verify_after_write": out["verify_after_write"].get("value", {}).get("result"),
        "verify_classification": out["verify_after_write"].get("value", {}).get("classification"),
        "redaction_passed_entry_check_and_waited": il.get("redaction_waiting"),
        "writer_not_blocked_by_marker_or_lock": il.get("writer_returned_while_lock_held") and
        (il.get("write") or {}).get("ok"),
        "target_live_after_write": sum((il.get("live_rows_after_write") or {}).values()) > 0,
        "tombstones_written_after_writer_commit": ij.get("tombstoned_after_writer_committed"),
        "final_refused_live": (not (il.get("redact") or {}).get("ok", True))
        and "live" in (il.get("redact") or {}).get("error", ""),
        "marker_held": bool(out["marker_after"].get("in_progress")),
        "verify_in_progress": out["verify_after_run"].get("value", {}).get("result"),
        "ledger_commit_refused": not out["ledger_commit_into_target"]["ok"],
        "rerun_refused": not out["rerun"]["ok"],
    }
    return out


def case_fk_guard(c: Conn) -> dict:
    reset(c)
    out = {}
    for name, sql, args in (
        ("edge_without_endpoints", "INSERT INTO Graph_KG.rdf_edges (s, p, o_id, graph_id) VALUES (?, ?, ?, '')",
         ["wsfk|a", "R", "wsfk|b"]),
        ("label_without_node", "INSERT INTO Graph_KG.rdf_labels (graph_id, s, label) VALUES ('', ?, ?)",
         ["wsfk|a", "L"]),
        ("prop_without_node", "INSERT INTO Graph_KG.rdf_props (graph_id, s, \"key\", val) VALUES ('', ?, ?, ?)",
         ["wsfk|a", "k", "v"]),
    ):
        out[name] = err(lambda: c.sql(sql, *args))
        c.conn.commit()
    out["live_rows_after"] = live_rows(c, "wsfk")
    reset(c)
    out["verdict"] = {"edge_refused": not out["edge_without_endpoints"]["ok"],
                      "label_refused": not out["label_without_node"]["ok"],
                      "prop_accepted_without_node": out["prop_without_node"]["ok"]}
    return out


def case_rb_delete_reification(c: Conn) -> dict:
    reset(c)
    smap = journal.storage_map(c)
    e = eng(c)
    e.ledger.enable()
    T = "wsrb"
    out = {"writer": "iris_vector_graph/_engine/schema.py::delete_reification"}
    rev = e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="wsrb content")
                          .create_node(f"{T}|n1", labels=["T"], properties={"secret": "wsrb-s1"}))
    out["target_revision"] = rev.revision.seq
    out["verify_before"] = verify(e)
    out["live_before"] = live_rows(c, T)
    cC = Conn(NS)
    try:
        eC = eng(cC)
        m = journal.mark()
        out["caller_start_transaction"] = err(lambda: cC.sql("START TRANSACTION"))
        out["tlevel_caller"] = cC.sql("SELECT $TLEVEL")[0][0]
        out["delete_reification"] = err(lambda: eC.delete_reification(f"{T}|n1"))
        out["tlevel_after_delete"] = cC.sql("SELECT $TLEVEL")[0][0]
        out["live_seen_by_other_connection_uncommitted"] = live_rows(c, T)
        out["redact_while_delete_uncommitted"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix=T)))
        out["marker_after_redact"] = marker(c)
        out["caller_rollback"] = err(lambda: cC.sql("ROLLBACK"))
        out["tlevel_after_rollback"] = cC.sql("SELECT $TLEVEL")[0][0]
        recs = jrecs(m, [cC.pid, c.pid])
        out["journal"] = {"caller_content_writes": content_writes(recs, smap, cC.pid),
                          "caller_transactions": [{k: u[k] for k in ("kind", "committed", "rolled_back")}
                                                  for u in journal.transactions([r for r in recs if r["p"] == str(cC.pid)])],
                          "redaction_ledger_writes": ledger_writes(recs, c.pid),
                          "tombstones": len(tombstone_addrs(recs, c.pid))}
    finally:
        cC.close()
    out["live_after_rollback"] = live_rows(c, T)
    out["node_after_rollback"] = c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id = ?", f"{T}|n1")
    out["records_of_target"] = [r for r in ledger_recs(c) if r["seq"] == str(out["target_revision"])]
    out["verify_after"] = verify(e)
    # phase 2 (INV-marker): the same with a bounded run that leaves the marker while the delete is uncommitted
    T2 = "wsrb2"
    e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="wsrb2 content")
                    .create_node(f"{T2}|n1", labels=["T"], properties={"secret": "wsrb2-s1"}))
    cC = Conn(NS)
    try:
        eC = eng(cC)
        p2 = {"start": err(lambda: cC.sql("START TRANSACTION"))}
        p2["delete_reification"] = err(lambda: eC.delete_reification(f"{T2}|n1"))
        p2["bounded_run"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix=T2, batch_size=1, max_batches=1)))
        p2["marker_before_rollback"] = marker(c)
        p2["rollback"] = err(lambda: cC.sql("ROLLBACK"))
    finally:
        cC.close()
    p2["marker_after_rollback"] = marker(c)
    p2["live_after_rollback"] = live_rows(c, T2)
    p2["rerun"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix=T2)))
    out["phase2_bounded"] = p2
    reset(c)
    rd = out["redact_while_delete_uncommitted"]
    out["verdict"] = {
        "delete_nested_in_caller_txn": out["tlevel_after_delete"] >= 1,
        "redaction_completed_while_delete_uncommitted": rd["ok"] and bool(rd["value"].get("complete")),
        "content_live_after_rollback": sum(out["live_after_rollback"].values()) > 0,
        "records_tombstoned": all(r["op"] == "redacted" for r in out["records_of_target"]) and bool(out["records_of_target"]),
        "verify_after": out["verify_after"].get("value", {}).get("result"),
        "phase2_marker_names_target_while_live": bool(out["phase2_bounded"]["marker_after_rollback"].get("in_progress"))
        and sum(out["phase2_bounded"]["live_after_rollback"].values()) > 0,
        "phase2_rerun_refused": not out["phase2_bounded"]["rerun"]["ok"],
    }
    return out


def _stmt_of(c: Conn, s, p, o, gkey="\x01"):
    sid = c.o.get("^IVG.Ledger", "tuple", s, p, o, gkey)
    if sid is None:
        return None, None
    row = c.o.getIRISList("^IVG.Ledger", "stmt", sid)
    return str(sid), (None if row is None else [str(row.get(i) or "") for i in range(1, 7)])


def case_stmt_collision(c: Conn) -> dict:
    reset(c)
    e = eng(c)
    e.ledger.enable()
    out = {}
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="marker-key qualifiers")
    for n in ("a", "b", "c", "d", "x", "y"):
        cs.create_node(f"wsq|{n}")
    cs.create_relationship("wsq|a", "RT", "wsq|b", qualifiers={"temporal": 1})      # RetractTemporalRow
    cs.create_relationship("wsq|c", "RD", "wsq|d", qualifiers={"temporal": 1})      # DropRows
    cs.create_relationship("wsq|x", "RI", "wsq|y", qualifiers={"inferred": "user"})    # retract_inference
    out["commit"] = err(lambda: e.ledger.commit(cs).revision.seq)
    out["rows_before"] = c.sql("SELECT s, p, o_id, qualifiers FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'wsq|'")
    out["stmts_before"] = {k: _stmt_of(c, *t) for k, t in (("RT", ("wsq|a", "RT", "wsq|b")),
                                                          ("RD", ("wsq|c", "RD", "wsq|d")),
                                                          ("RI", ("wsq|x", "RI", "wsq|y")))}
    out["verify_before"] = verify(e)
    # (a) a temporal edge on the same triple, then its deletion (TemporalIndex.DeleteTemporalEdge ->
    #     Adjacency.RetractTemporalRow, temporal.py:375-389)
    out["a_create_edge_temporal"] = err(lambda: e.create_edge_temporal("wsq|a", "RT", "wsq|b", timestamp=TS))
    out["a_delete_edge_temporal"] = err(lambda: e.delete_edge_temporal("wsq|a", "RT", "wsq|b", TS))
    c.conn.commit()
    # (b) TemporalPolicy.DropRows for a predicate registered temporal-only
    out["b_set_temporal_only"] = err(lambda: e.set_temporal_structural("RD", False))
    out["b_drop_rows"] = err(lambda: str(e.drop_temporal_structural_rows("RD")))
    c.conn.commit()
    # (c) retract_inference in the default graph
    out["c_retract_inference"] = err(lambda: e.retract_inference())
    c.conn.commit()
    out["rows_after"] = c.sql("SELECT s, p, o_id, qualifiers FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'wsq|'")
    out["stmts_after"] = {k: _stmt_of(c, *t) for k, t in (("RT", ("wsq|a", "RT", "wsq|b")),
                                                         ("RD", ("wsq|c", "RD", "wsq|d")),
                                                         ("RI", ("wsq|x", "RI", "wsq|y")))}
    out["verify_after"] = verify(e)
    reset(c)
    rows_after = {(r[0], r[1]) for r in out["rows_after"]}

    def lost(k, s):
        sid, row = out["stmts_after"][k]
        return (s, k) not in rows_after and sid is not None and row is not None and row[5] == ""
    out["verdict"] = {
        "RetractTemporalRow_deleted_recorded_row_stmt_live": lost("RT", "wsq|a"),
        "DropRows_deleted_recorded_row_stmt_live": lost("RD", "wsq|c"),
        "retract_inference_deleted_recorded_row_stmt_live": lost("RI", "wsq|x"),
        "verify_after": out["verify_after"].get("value", {}).get("result"),
        "verify_classification": out["verify_after"].get("value", {}).get("classification"),
    }
    return out


def _docker(*args) -> str:
    r = subprocess.run(["docker", "exec", os.environ["IVG_TEST_CONTAINER"], *args], capture_output=True, text=True,
                       timeout=60)
    return (r.stdout + r.stderr)[-400:]


def case_snap_helpers(c: Conn) -> dict:
    reset(c)
    smap = journal.storage_map(c)
    out = {"storage_globals_of_invariant_stores": {k: v for k, v in smap.items()
                                                   if v.split(".")[-1] in ("nodes", "rdf_labels", "rdf_props",
                                                                           "rdf_edges", "ledger_revisions",
                                                                           "LedgerRevision")}}
    # SetNodeJSON: NodeRef's allow-list (Snapshot.cls:92-105)
    for g, subs in (("^IVG.Ledger", ["redacting"]), ("^IVG.Ledger", ["rec", 1, 1]),
                    ("^Graph.KG.LedgerRevisionD", [1])):
        out[f"setnodejson {g}{subs}"] = err(lambda: c.o.classMethodVoid("Graph.KG.Snapshot", "SetNodeJSON", g,
                                                                         json.dumps(subs), json.dumps({"v": "x"})))
    out["ivg_ledger_after_setnodejson"] = c.o.isDefined("^IVG.Ledger", "redacting")
    for root in smap:
        if root.rstrip(".") in ("^IVF", "^PLAID", "^VecIdx"):
            out.setdefault("storage_in_allow_list", []).append(root)
    # ImportGlobals: export ledger history H1, replace it with H2, import H1's file
    e = eng(c)
    e.ledger.enable()
    e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="H1")
                    .create_node("wsimp1|n1", labels=["H1"], properties={"secret": "h1"}))
    d = f"/tmp/IVGAuditWS-{int(time.time())}/"
    out["export"] = err(lambda: str(c.call("Graph.KG.Snapshot", "ExportGlobals", d, json.dumps([{"name": "^IVG.Ledger"}]))))
    if "gof" not in out["export"].get("value", ""):
        out["export_without_caret"] = err(lambda: str(c.call("Graph.KG.Snapshot", "ExportGlobals", d,
                                                             json.dumps([{"name": "IVG.Ledger"}]))))
    out["files"] = _docker("ls", "-la", d)
    h1 = ledger_recs(c)
    reset(c)
    e.ledger.enable()
    e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="H2")
                    .create_node("wsimp2|n1", labels=["H2"], properties={"secret": "h2"}))
    h2 = ledger_recs(c)
    out["verify_before_import"] = verify(e)
    m = journal.mark()
    out["import"] = err(lambda: str(c.call("Graph.KG.Snapshot", "ImportGlobals", d)))
    recs = jrecs(m, [c.pid])
    out["import_journal_ledger_writes"] = ledger_writes(recs, c.pid)
    h3 = ledger_recs(c)
    out["records"] = {"H1": h1, "H2": h2, "after_import": h3}
    out["revision_rows_after_import"] = c.sql("SELECT seq, message FROM Graph_KG.ledger_revisions ORDER BY seq")
    out["verify_after_import"] = verify(e)
    out["cleanup_dir"] = _docker("rm", "-rf", d)
    reset(c)
    ids3 = {r["id"] for r in h3}
    out["verdict"] = {
        "setnodejson_refused_ledger": all(not out[k]["ok"] for k in out if k.startswith("setnodejson")),
        "no_invariant_store_in_allow_list": not out.get("storage_in_allow_list"),
        "import_wrote_ledger_global": bool(out["import_journal_ledger_writes"]),
        "record_replaced_by_other_history": "wsimp1|n1" in ids3 and "wsimp2|n1" not in ids3,
        "verify_after_import": out["verify_after_import"].get("value", {}).get("result"),
    }
    return out


def case_sql_insert(c: Conn, wedge: bool = True) -> dict:
    reset(c)
    e = eng(c)
    e.ledger.enable()
    out = {}
    r = e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="secret message wssql",
                                  idempotency_key="wssql-k1").create_node("wssql|n1", properties={"s": "x"}))
    seq = r.revision.seq
    e.delete_nodes_by_prefix("wssql|")
    c.conn.commit()
    out["redact"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="wssql")))
    out["row_after_redaction"] = c.sql("SELECT seq, message, idempotency_key FROM Graph_KG.ledger_revisions WHERE seq = ?", seq)
    cols = [r[0] for r in c.sql("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='Graph_KG' "
                                "AND TABLE_NAME='ledger_revisions' ORDER BY ORDINAL_POSITION")]
    out["columns"] = cols
    ins = ("INSERT INTO Graph_KG.ledger_revisions (seq, revision_id, parent_id, kind, actor, actor_type, conn_user, "
           "committed_ms, message, source, correlation_id, idempotency_key, op_count) "
           "VALUES (?, ?, ?, 'changeset', 'audit:writesets', 'ingest', '_SYSTEM', ?, ?, NULL, NULL, ?, 1)")
    out["insert_same_seq"] = err(lambda: c.sql(ins, seq, "wssqlrev", "p", int(time.time() * 1000), "text back",
                                               "wssql-k1"))
    c.conn.commit()
    out["update_message"] = err(lambda: c.sql("UPDATE Graph_KG.ledger_revisions SET message = ? WHERE seq = ?",
                                              "text back", seq))
    c.conn.commit()
    out["row_after_attempts"] = c.sql("SELECT seq, message, idempotency_key FROM Graph_KG.ledger_revisions WHERE seq = ?", seq)
    if not wedge:
        out["verify_after"] = verify(e)
        reset(c)
        out["verdict"] = {
            "text_cleared_by_redaction": bool(out["row_after_redaction"]) and out["row_after_redaction"][0][1] in (None, ""),
            "insert_same_seq_refused": not out["insert_same_seq"]["ok"],
            "update_refused": not out["update_message"]["ok"],
            "text_still_cleared": bool(out["row_after_attempts"]) and out["row_after_attempts"][0][1] in (None, ""),
            "verify_after": out["verify_after"].get("value", {}).get("result"),
        }
        return out
    head = int(json.loads(str(c.call("Graph.KG.Ledger", "Meta")))["head_seq"])
    out["head_before_planting"] = head
    out["insert_next_seq"] = err(lambda: c.sql(ins, head + 1, "wssqlnext", "p", int(time.time() * 1000), "planted",
                                               None))
    c.conn.commit()
    out["commit_after_planted_row"] = err(lambda: e.ledger.commit(
        Changeset(actor="audit:writesets", actor_type="ingest").create_node("wssql2|n1")).revision.seq)
    out["verify_after"] = verify(e)
    reset(c)
    out["verdict"] = {
        "text_cleared_by_redaction": out["row_after_redaction"] and out["row_after_redaction"][0][1] in (None, ""),
        "insert_same_seq_refused": not out["insert_same_seq"]["ok"],
        "update_refused": not out["update_message"]["ok"],
        "text_still_cleared": out["row_after_attempts"] and out["row_after_attempts"][0][1] in (None, ""),
        "insert_next_seq_accepted": out["insert_next_seq"]["ok"],
        "next_commit_refused": not out["commit_after_planted_row"]["ok"],
        "verify_after": out["verify_after"].get("value", {}).get("result"),
    }
    return out


def case_gap_marker(c: Conn) -> dict:
    """WS-GAP-001: a marker the live ledger holds survives a replacing restore that brings the target's content back."""
    reset(c)
    e = eng(c)
    e.ledger.enable()
    out = {}
    for i in range(3):
        e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message=f"wsgm {i}")
                        .create_node(f"wsgm|n{i}", labels=["G"], properties={"secret": f"wsgm-s{i}"}))
    arch = str(OUT / f"gap-marker-{int(time.time())}.ivgsnap")
    out["save"] = err(lambda: str(e.save_snapshot(arch))[:200])
    e.delete_nodes_by_prefix("wsgm|")
    c.conn.commit()
    out["bounded_run"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="wsgm", batch_size=1, max_batches=1)))
    out["marker_before_restore"] = marker(c)
    out["live_before_restore"] = live_rows(c, "wsgm")
    out["restore"] = err(lambda: str(e.restore_snapshot(arch, merge=False))[:200])
    c.conn.commit()
    out["marker_after_restore"] = marker(c)
    out["live_after_restore"] = live_rows(c, "wsgm")
    out["tombstones_after_restore"] = sum(1 for r in ledger_recs(c) if r["op"] == "redacted")
    out["verify_after_restore"] = verify(e)
    out["rerun"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="wsgm")))
    out["ledger_commit_other_tenant"] = err(lambda: e.ledger.commit(
        Changeset(actor="audit:writesets", actor_type="ingest").create_node("wsgmB|n1")).revision.seq)
    reset(c)
    out["verdict"] = {
        "marker_before": bool(out["marker_before_restore"].get("in_progress")),
        "marker_survives_restore": bool(out["marker_after_restore"].get("in_progress")),
        "target_live_after_restore": sum(out["live_after_restore"].values()) > 0,
        "INV_marker_violated": bool(out["marker_after_restore"].get("in_progress"))
        and sum(out["live_after_restore"].values()) > 0,
        "rerun_refused": not out["rerun"]["ok"],
    }
    return out


def case_gap_restore(c: Conn) -> dict:
    reset(c)
    e = eng(c)
    e.ledger.enable()
    out = {}
    r = e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="wsgap secret message",
                                  idempotency_key="wsgap-k1").create_node("wsgap|n1", labels=["G"],
                                                                          properties={"secret": "wsgap-s"}))
    seq = r.revision.seq
    arch = str(OUT / f"gap-restore-{int(time.time())}.ivgsnap")
    out["save"] = err(lambda: str(e.save_snapshot(arch))[:300])
    e.delete_nodes_by_prefix("wsgap|")
    c.conn.commit()
    out["redact1"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="wsgap")))

    def state():
        return {"row": c.sql("SELECT seq, message, idempotency_key FROM Graph_KG.ledger_revisions WHERE seq = ?", seq),
                "recs": [x for x in ledger_recs(c) if x["seq"] == str(seq)],
                "redactedRev": c.o.isDefined("^IVG.Ledger", "redactedRev", seq),
                "idem_live": c.o.isDefined("^IVG.Ledger", "idem", "wsgap-k1"),
                "idemRedacted_n": sum(1 for _ in c.o.iterator("^IVG.Ledger", "idemRedacted").items()),
                "marker": marker(c)}
    out["after_redact1"] = state()
    out["restore"] = err(lambda: str(e.restore_snapshot(arch, merge=False))[:300])
    c.conn.commit()
    out["after_restore"] = state()
    out["live_after_restore"] = live_rows(c, "wsgap")
    e.delete_nodes_by_prefix("wsgap|")
    c.conn.commit()
    out["redact2"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="wsgap")))
    out["after_redact2"] = state()
    out["retry_with_key"] = err(lambda: str(e.ledger.commit(
        Changeset(actor="audit:writesets", actor_type="ingest", idempotency_key="wsgap-k1")
        .create_node("wsgap|n1", labels=["G"], properties={"secret": "wsgap-s"}))))
    out["verify_after"] = verify(e)
    reset(c)
    a2 = out["after_redact2"]
    tomb2 = bool(a2["recs"]) and all(x["op"] == "redacted" for x in a2["recs"])
    out["verdict"] = {
        "restore_left_redactedRev_with_live_records": bool(out["after_restore"]["redactedRev"]) and
        not all(x["op"] == "redacted" for x in out["after_restore"]["recs"]),
        "second_redaction_tombstoned": tomb2,
        "INV_text_violated": tomb2 and bool(a2["row"]) and a2["row"][0][1] not in (None, ""),
        "INV_retry_violated": tomb2 and bool(a2["idem_live"]),
    }
    return out


def case_snap_setnodejson(c: Conn) -> dict:
    """SetNodeJSON's NodeRef allow-list (Snapshot.cls:92-105) against every store the 8 invariants read."""
    reset(c)
    smap = journal.storage_map(c)
    e = eng(c)
    e.ledger.enable()
    e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="wssn")
                    .create_node("wssn|n1", labels=["S"], properties={"secret": "s"}))
    inv_globals = sorted(k for k, v in smap.items() if v.split(".")[-1] in
                         ("nodes", "rdf_labels", "rdf_props", "rdf_edges", "ledger_revisions"))
    out = {"invariant_store_globals": ["^IVG.Ledger"] + inv_globals}
    m = journal.mark()
    tries = {}
    for g in out["invariant_store_globals"]:
        for subs in (["redacting"], ["rec", 2, 1], ["idem", "k"], ["stmt", 1], [1]):
            tries[f"{g}{subs}"] = err(lambda: c.o.classMethodVoid("Graph.KG.Snapshot", "SetNodeJSON", g.rstrip("."),
                                                                   json.dumps(subs), json.dumps({"v": "x"})))
    out["setnodejson"] = tries
    recs = jrecs(m, [c.pid])
    out["journal_sets_by_setnodejson_process"] = [r["g"] for r in recs if r["g"]][:20]
    out["allowed_globals_in_storage_map"] = [k for k in smap if k.rstrip(".") in ("^IVF", "^PLAID", "^VecIdx")]
    out["verify_after"] = verify(e)
    reset(c)
    out["verdict"] = {
        "every_call_refused": all(not v["ok"] for v in tries.values()),
        "refusal_text": sorted({v.get("error", "")[-60:] for v in tries.values()})[:3],
        "no_global_written": not out["journal_sets_by_setnodejson_process"],
        "no_invariant_store_in_allow_list": not out["allowed_globals_in_storage_map"],
        "verify_after": out["verify_after"].get("value", {}).get("result"),
    }
    return out


def case_stmt_purge(c: Conn) -> dict:
    """INV-stmt for Adjacency.RetractTemporalRows: the purge (TemporalIndex.PurgeBefore -> RetireExpired) on a
    ledger relationship whose qualifiers carry temporal=1 and a temporal edge on the same triple."""
    reset(c)
    e = eng(c)
    e.ledger.enable()
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="purge collision")
    cs.create_node("wsp|a", labels=["P"]).create_node("wsp|b", labels=["P"])
    cs.create_relationship("wsp|a", "RP", "wsp|b", qualifiers={"temporal": 1})
    out = {"commit": err(lambda: e.ledger.commit(cs).revision.seq)}
    out["rows_before"] = c.sql("SELECT s, p, o_id, qualifiers FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'wsp|'")
    out["stmt_before"] = _stmt_of(c, "wsp|a", "RP", "wsp|b")
    out["verify_before"] = verify(e)
    out["create_edge_temporal_old"] = err(lambda: e.create_edge_temporal("wsp|a", "RP", "wsp|b", timestamp=1000))
    out["purge_before"] = err(lambda: e.purge_before(2000))
    c.conn.commit()
    out["rows_after"] = c.sql("SELECT s, p, o_id, qualifiers FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'wsp|'")
    out["stmt_after"] = _stmt_of(c, "wsp|a", "RP", "wsp|b")
    out["verify_after"] = verify(e)
    reset(c)
    sid, row = out["stmt_after"]
    out["verdict"] = {"recorded_row_deleted": not out["rows_after"],
                      "stmt_live_without_row": (not out["rows_after"]) and sid is not None and row is not None
                      and row[5] == "",
                      "verify_after": out["verify_after"].get("value", {}).get("result")}
    return out


def case_migrations(c: Conn) -> dict:
    """schema.py migrations that initialize_schema runs on every call (ensure_indexes, schema.py:704-722), while a
    redaction marker exists: tighten_graph_id_column, ensure_ekey (via _spo_constraint_status),
    ensure_props_value_key, and add_graph_id_to_nodes on a node a bypass writer gave a '__graph' property."""
    from iris_vector_graph.schema import GraphSchema
    reset(c)
    e = eng(c)
    e.ledger.enable()
    G = "wsagG"
    out = {}
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="wsag graph content")
    cs.create_node("wsag|x", labels=["A"]).create_node("wsag|y", labels=["A"])
    cs.create_relationship("wsag|x", "R", "wsag|y", graph=G)
    out["commit"] = err(lambda: e.ledger.commit(cs).revision.seq)
    out["live_G_before_erase"] = live_rows(c, "", G)
    out["erase_graph"] = err(lambda: e.erase_graph(G))
    c.conn.commit()
    out["bounded_run"] = err(lambda: receipt_dict(e.ledger.redact(G, batch_size=1, max_batches=1)))
    out["marker"] = marker(c)
    recs0 = ledger_recs(c)
    out["live_G_with_marker"] = live_rows(c, "", G)
    cur = c.conn.cursor()
    for name, fn in (("tighten_graph_id_column", GraphSchema.tighten_graph_id_column),
                     ("spo_constraint_status_ensure_ekey", GraphSchema._spo_constraint_status),
                     ("ensure_props_value_key", GraphSchema.ensure_props_value_key)):
        out[name] = err(lambda: str(fn(cur))[:300])
        c.conn.commit()
        out[name + "_live_G"] = live_rows(c, "", G)
    out["records_unchanged_by_three"] = ledger_recs(c) == recs0
    # a bypass writer's '__graph' property, then add_graph_id_to_nodes
    out["create_node_with___graph"] = err(lambda: e.create_node("wsag|z", properties={"__graph": G}))
    c.conn.commit()
    out["z_rows_before"] = {"nodes": c.sql("SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id = 'wsag|z'"),
                            "props": c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = 'wsag|z'")}
    out["add_graph_id_to_nodes"] = err(lambda: str(GraphSchema.add_graph_id_to_nodes(cur))[:300])
    c.conn.commit()
    out["z_rows_after"] = {"nodes": c.sql("SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id = 'wsag|z'"),
                           "props": c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = 'wsag|z'")}
    out["live_G_after_add_graph_id"] = live_rows(c, "", G)
    out["marker_after"] = marker(c)
    out["rerun"] = err(lambda: receipt_dict(e.ledger.redact(G)))
    cur.close()
    reset(c)
    three_ok = all(sum(out[n + "_live_G"].values()) == 0 for n in
                   ("tighten_graph_id_column", "spo_constraint_status_ensure_ekey", "ensure_props_value_key"))
    out["verdict"] = {
        "marker_set": bool(out["marker"].get("in_progress")),
        "three_migrations_left_target_not_live": three_ok,
        "three_migrations_left_records": out["records_unchanged_by_three"],
        "bypass_wrote___graph_prop": any(r[1] == "__graph" for r in out["z_rows_before"]["props"]),
        "add_graph_id_moved_node_into_marked_graph": any(r[1] == G for r in out["z_rows_after"]["nodes"]),
        "INV_marker_violated": bool(out["marker_after"].get("in_progress")) and
        sum(out["live_G_after_add_graph_id"].values()) > 0,
        "rerun_refused": not out["rerun"]["ok"],
    }
    return out


def case_fhir_blocked(c: Conn) -> dict:
    out = {"register": err(lambda: str(c.call("Graph.KG.FHIRGraph", "Register", "ws-none")))}
    out["hs_fhirserver_classes"] = c.sql("SELECT COUNT(*) FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'HS.FHIRServer'")
    out["verdict"] = {"register_refused": "no FHIR repository" in json.dumps(out["register"]),
                      "hs_fhirserver_class_count": out["hs_fhirserver_classes"][0][0]}
    return out


def case_noindex(c: Conn) -> dict:
    """BulkLoader.load_nodes' %NOINDEX rows against the redaction's liveness check (LiveRows reads through indexes)."""
    from iris_vector_graph.bulk_loader import BulkLoader
    reset(c)
    smap = journal.storage_map(c)
    e = eng(c)
    e.ledger.enable()
    T = "wsni"
    e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="wsni content")
                    .create_node(f"{T}|n1", labels=["T"], properties={"secret": "wsni-s1"}))
    e.delete_nodes_by_prefix(f"{T}|")
    c.conn.commit()
    out = {"live_after_erase": live_rows(c, T)}
    cL = Conn(NS)
    try:
        m = journal.mark()
        out["load_nodes"] = err(lambda: str(BulkLoader(cL.conn).load_nodes([(f"{T}|n1", {"namespace": "T",
                                                                                         "secret": "loaded"})])))
        cL.conn.commit()
        recs = jrecs(m, [cL.pid])
        out["loader_content_writes"] = content_writes(recs, smap, cL.pid)
    finally:
        cL.close()

    def scan():
        return {t: c.sql(f"SELECT COUNT(*) FROM %IGNOREINDEX * Graph_KG.{t} WHERE {col} %STARTSWITH ?", f"{T}|")[0][0]
                for t, col in (("nodes", "node_id"), ("rdf_labels", "s"), ("rdf_props", "s"))}
    out["live_rows_indexed_count"] = live_rows(c, T)
    out["rows_by_full_scan"] = err(scan)
    out["redact"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix=T)))
    out["marker_after"] = marker(c)
    out["records"] = [r for r in ledger_recs(c) if r["seq"] == "2"]
    out["rebuild"] = err(lambda: str(BulkLoader(c.conn).rebuild_all_indices())[:200])
    c.conn.commit()
    out["live_rows_after_rebuild"] = live_rows(c, T)
    out["verify_after"] = verify(e)
    reset(c)
    full = (out["rows_by_full_scan"].get("value") or {})
    out["verdict"] = {
        "loader_wrote_rows": bool(out["loader_content_writes"]),
        "liveness_count_missed_rows": sum(out["live_rows_indexed_count"].values()) == 0 and sum(full.values()) > 0,
        "redaction_completed": bool(out["redact"].get("ok") and out["redact"]["value"].get("complete")),
        "records_tombstoned": bool(out["records"]) and all(r["op"] == "redacted" for r in out["records"]),
        "live_after_rebuild": sum(out["live_rows_after_rebuild"].values()) > 0,
        "verify_after": out["verify_after"].get("value", {}).get("result"),
    }
    return out


# ----------------------------------------------------------------------------------- review R4-02 / R4-06 reruns

def fullscan(c: Conn, prefix: str | None = None) -> dict:
    """Row counts read without any index (%IGNOREINDEX *), whole table or for one id prefix."""
    out = {}
    for t, cols in (("nodes", ("node_id",)), ("rdf_labels", ("s",)), ("rdf_props", ("s",)), ("rdf_edges", ("s", "o_id"))):
        q = f"SELECT COUNT(*) FROM %IGNOREINDEX * Graph_KG.{t}"
        if prefix is None:
            out[t] = c.sql(q)[0][0]
        else:
            w = " OR ".join(f"{col} %STARTSWITH ?" for col in cols)
            out[t] = c.sql(q + f" WHERE {w}", *([prefix] * len(cols)))[0][0]
    return out


def case_replay_delete_reification(c: Conn) -> dict:
    """INV-replay for delete_reification with a committed delete (review R4-02): no caller transaction."""
    reset(c)
    smap = journal.storage_map(c)
    out = {"residue_fullscan_after_reset": fullscan(c)}
    e = eng(c)
    e.ledger.enable()
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="control")
    cs.create_node("wsctl|n1", labels=["C"], properties={"k": "v"})
    e.ledger.commit(cs)
    T = "wsrd"
    e.ledger.commit(Changeset(actor="audit:writesets", actor_type="ingest", message="wsrd content")
                    .create_node(f"{T}|n1", labels=["T"], properties={"secret": "wsrd-s1"}))
    out["verify_baseline"] = verify(e)
    cW = Conn(NS)
    try:
        eW = eng(cW)
        out["tlevel_before"] = cW.sql("SELECT $TLEVEL")[0][0]
        m = journal.mark()
        out["delete_reification"] = err(lambda: eW.delete_reification(f"{T}|n1"))
        out["tlevel_after"] = cW.sql("SELECT $TLEVEL")[0][0]
        recs = jrecs(m, [cW.pid])
        out["journal"] = {"content_writes": content_writes(recs, smap, cW.pid),
                          "ledger_writes": ledger_writes(recs, cW.pid),
                          "transactions": [{k: u[k] for k in ("kind", "committed", "rolled_back")}
                                           for u in journal.transactions(recs)]}
    finally:
        cW.close()
    out["live_rows_after"] = live_rows(c, T)
    out["verify_after"] = verify(e)
    reset(c)
    v = out["verify_after"].get("value", {})
    out["verdict"] = {
        "baseline_equal": out["verify_baseline"].get("value", {}).get("result") == "equal",
        "delete_committed_no_caller_txn": out["tlevel_before"] == 0 and out["tlevel_after"] == 0
        and all(t["committed"] and not t["rolled_back"] for t in out["journal"]["transactions"]),
        "writer_wrote_content": bool(out["journal"]["content_writes"]),
        "writer_wrote_no_ledger_node": not out["journal"]["ledger_writes"],
        "verify_after": v.get("result"), "classification": v.get("classification"),
        "differences_name_the_deleted_node": any(f"{T}|n1" in x for x in v.get("differences", [])),
    }
    return out


def case_replay_import_rdf(c: Conn) -> dict:
    """INV-replay for import_rdf from an equal baseline (review R4-06): residue checked first."""
    reset(c)
    smap = journal.storage_map(c)
    out = {"residue_fullscan_after_reset": fullscan(c)}
    e = eng(c)
    e.ledger.enable()
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="control")
    cs.create_node("wsctl|n1", labels=["C"], properties={"k": "v"})
    e.ledger.commit(cs)
    out["verify_baseline"] = verify(e)
    D = "wsri"
    cW = Conn(NS)
    try:
        eW = eng(cW)
        m = journal.mark()
        out["import_rdf"] = err(lambda: str(eW.import_rdf(_rdf_file(D))))
        cW.conn.commit()
        recs = jrecs(m, [cW.pid])
        out["journal"] = {"content_writes": content_writes(recs, smap, cW.pid),
                          "ledger_writes": ledger_writes(recs, cW.pid)}
    finally:
        cW.close()
    out["verify_after_write"] = verify(e)
    out["erase"] = err(lambda: erase_form(e, c, "urn", D))
    out["fullscan_D_after_erase"] = fullscan(c, f"urn:{D}:")
    out["verify_after_erase"] = verify(e)
    reset(c)
    v = out["verify_after_write"].get("value", {})
    out["verdict"] = {
        "baseline_equal": out["verify_baseline"].get("value", {}).get("result") == "equal",
        "writer_wrote_content": bool(out["journal"]["content_writes"]),
        "writer_wrote_no_ledger_node": not out["journal"]["ledger_writes"],
        "verify_after_write": v.get("result"), "classification": v.get("classification"),
        "differences_name_imported_ids": any(f"urn:{D}:" in x for x in v.get("differences", [])),
        "verify_after_erase": out["verify_after_erase"].get("value", {}).get("result"),
    }
    return out


def case_noindex_erase(c: Conn) -> dict:
    """The %NOINDEX edge row a BulkLoader.load_edges writes, against delete_nodes_by_prefix and EraseAll+PurgeAll
    (review R4-06: the residue seen in ws-live-ins-bulkloader_load_edges / -import_rdf)."""
    from iris_vector_graph.bulk_loader import BulkLoader
    reset(c)
    out = {"residue_fullscan_after_reset": fullscan(c)}
    e = eng(c)
    e.ledger.enable()
    P = "wse"
    cL = Conn(NS)
    try:
        out["load_edges"] = err(lambda: str(BulkLoader(cL.conn).load_edges([(f"{P}|a", "R", f"{P}|b", None)])))
        cL.conn.commit()
    finally:
        cL.close()
    out["after_load"] = {"indexed": live_rows(c, P), "fullscan": fullscan(c, f"{P}|")}
    out["verify_after_load"] = verify(e)
    out["delete_nodes_by_prefix"] = err(lambda: e.delete_nodes_by_prefix(f"{P}|"))
    c.conn.commit()
    out["after_prefix_erase"] = {"indexed": live_rows(c, P), "fullscan": fullscan(c, f"{P}|"),
                                 "edge_row": c.sql("SELECT %ID, s, p, o_id, graph_id FROM %IGNOREINDEX * "
                                                   "Graph_KG.rdf_edges WHERE s %STARTSWITH ?", f"{P}|")}
    out["verify_after_prefix_erase"] = verify(e)
    out["erase_all"] = err(lambda: str(c.call("Graph.KG.Eraser", "EraseAll")))
    out["purge_all"] = err(lambda: str(c.call("Graph.KG.Ledger", "PurgeAll")))
    c.conn.commit()
    out["after_eraseall_purgeall"] = {"indexed": live_rows(c, P), "fullscan": fullscan(c, f"{P}|"),
                                      "fullscan_all": fullscan(c)}
    e.ledger.enable()
    out["verify_after_eraseall_reenable"] = verify(e)
    out["rebuild_all_indices"] = err(lambda: str(BulkLoader(c.conn).rebuild_all_indices())[:200])
    c.conn.commit()
    out["after_rebuild"] = {"indexed": live_rows(c, P), "fullscan": fullscan(c, f"{P}|")}
    reset(c)
    out["after_final_reset_fullscan_all"] = fullscan(c)
    ape, aea = out["after_prefix_erase"], out["after_eraseall_purgeall"]
    out["verdict"] = {
        "edge_row_unindexed_after_load": out["after_load"]["indexed"]["rdf_edges"] == 0
        and out["after_load"]["fullscan"]["rdf_edges"] == 1,
        "prefix_erase_removed_nodes": ape["fullscan"]["nodes"] == 0,
        "edge_row_survives_prefix_erase": ape["fullscan"]["rdf_edges"] == 1,
        "edge_row_survives_eraseall_purgeall": aea["fullscan"]["rdf_edges"] == 1,
        "verify_after_eraseall_reenable": out["verify_after_eraseall_reenable"].get("value", {}).get("result"),
        "visible_after_rebuild": out["after_rebuild"]["indexed"]["rdf_edges"],
        "clean_after_rebuild_and_reset": sum(out["after_final_reset_fullscan_all"].values()) == 0,
    }
    return out


CASES = {f"ins-{k}": (lambda k: (lambda c: case_ins(c, k)))(k) for k in WRITERS}
CASES.update({"fk-guard": case_fk_guard, "rb-delete_reification": case_rb_delete_reification,
              "stmt-collision": case_stmt_collision, "snap-helpers": case_snap_helpers,
              "sql-insert": case_sql_insert, "sql-guard": lambda c: case_sql_insert(c, wedge=False), "gap-restore": case_gap_restore,
              "gap-marker": case_gap_marker, "snap-setnodejson": case_snap_setnodejson,
              "stmt-purge": case_stmt_purge, "migrations": case_migrations, "fhir-blocked": case_fhir_blocked,
              "noindex": case_noindex, "replay-delete_reification": case_replay_delete_reification,
              "replay-import_rdf": case_replay_import_rdf, "noindex-erase": case_noindex_erase})


def main() -> int:
    want = sys.argv[1:]
    if want == ["ins-all"]:
        want = [k for k in CASES if k.startswith("ins-")]
    c = Conn(NS)
    print("engine:", version(c), "pid", c.pid, flush=True)
    rc = 0
    try:
        for name in want:
            t0 = time.time()
            try:
                res = CASES[name](c)
            except Exception as ex:
                rc = 1
                res = {"exception": f"{type(ex).__name__}: {ex}", "traceback": traceback.format_exc()[-4000:]}
                try:
                    reset(c)
                except Exception as ex2:
                    res["reset_error"] = str(ex2)
            res["case"] = name
            res["seconds"] = round(time.time() - t0, 2)
            res["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            res["namespace"] = NS
            (OUT / f"{name}.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
            print(name, json.dumps(res.get("verdict", res.get("exception")), default=str), flush=True)
    finally:
        c.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
