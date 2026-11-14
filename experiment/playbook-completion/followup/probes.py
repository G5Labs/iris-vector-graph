#!/usr/bin/env python3
"""Review follow-up (R-01a, R-03, R-04, R-10): live probes in namespace AUDITA through the pin's public Python API.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 \
        python experiment/playbook-completion/followup/probes.py [r01a r03 r04 ...]

Each check starts from an empty AUDITA (Graph.KG.Eraser.EraseAll + Graph.KG.Ledger.PurgeAll), builds its world with
the product's own calls (engine.ledger.commit, create_node, delete_nodes_by_prefix, save_snapshot, restore_snapshot,
set_temporal_structural, ledger.redact), records what it sees, and empties AUDITA again. Nothing is compiled, no
product file is touched, no scratch global is written. At most two connections are open at once (R-03 uses a second
one to hold the ledger head lock for a few seconds). Output: $RUN_DIR/followup/<check>.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
from iris_conn import Conn, version  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITA"
OUT = Path(os.environ["RUN_DIR"]) / "followup"
OUT.mkdir(parents=True, exist_ok=True)
ARCH = OUT / "archives"
ARCH.mkdir(exist_ok=True)


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
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)[:600]}


def receipt_dict(r) -> dict:
    d = {k: getattr(r, k) for k in ("complete", "target_sha256", "revision_seqs", "records_tombstoned",
                                     "metadata_cleared", "idempotency_keys_removed", "statements_removed",
                                     "unattributed_records", "batches", "out_of_reach")}
    d["redaction_seq"] = r.redaction.seq if r.redaction else None
    return d


def walk_global(o, gname: str, subs=(), out=None, limit=200000):
    """Every (subscripts, raw value bytes) node of a global, depth first."""
    out = [] if out is None else out
    d = o.isDefined(gname, *subs)
    if d in (1, 11) and subs:
        try:
            v = o.getBytes(gname, *subs)
        except Exception:
            v = str(o.get(gname, *subs)).encode()
        out.append((list(subs), v or b""))
    if d in (10, 11) or not subs:
        for k, _ in o.iterator(gname, *subs).items():
            if len(out) >= limit:
                break
            walk_global(o, gname, subs + (k,), out, limit)
    return out


def scan_ledger(c: Conn, tokens) -> dict:
    """SC-001's scan: every ^IVG.Ledger subscript and value and every Graph_KG.ledger_* row, per token."""
    hits = {t: {"global_nodes": [], "ledger_revisions": 0, "ledger_stats": 0} for t in tokens}
    for subs, v in walk_global(c.o, "^IVG.Ledger"):
        text = " ".join(str(s) for s in subs).encode() + b" " + v
        for t in tokens:
            if t.encode() in text:
                hits[t]["global_nodes"].append([str(s) for s in subs][:4])
    for table in ("ledger_revisions", "ledger_stats"):
        rows = c.sql(f"SELECT * FROM Graph_KG.{table}")
        for row in rows:
            s = " ".join("" if x is None else str(x) for x in row)
            for t in tokens:
                if t in s:
                    hits[t][table] += 1
    for t in tokens:
        hits[t]["global_node_count"] = len(hits[t]["global_nodes"])
        hits[t]["global_nodes"] = hits[t]["global_nodes"][:8]
    return hits


def scan_archive(path: str, tokens) -> dict:
    out = {t: {} for t in tokens}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            data = z.read(name)
            for t in tokens:
                n = data.count(t.encode())
                if n:
                    out[t][name] = n
    return out


def content_rows(c: Conn, prefix: str) -> dict:
    p = prefix + "%"
    return {
        "nodes": c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id LIKE ?", p)[0][0],
        "rdf_props": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s LIKE ?", p)[0][0],
        "rdf_labels": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE s LIKE ?", p)[0][0],
        "rdf_edges": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s LIKE ? OR o_id LIKE ?", p, p)[0][0],
    }


def marker(c: Conn):
    return json.loads(str(c.call("Graph.KG.LedgerRedact", "InProgress")))


# ------------------------------------------------------------------------------------------------- R-01(a) + R-10

def check_r01a(c: Conn) -> dict:
    """IVG's own snapshot archives keep a tenant after erase + redaction; a restore brings it back.

    The HTTP route POST /admin/snapshot (cypher_api.py:668-678) calls exactly eng.save_snapshot(path) with
    path = $IVG_SNAPSHOT_DIR or tempfile.gettempdir() / ivg_snapshot_<epoch>.snapshot; this probe calls the same
    method with a path of that shape under $RUN_DIR/followup/archives.
    """
    reset(c)
    e = eng(c)
    e.ledger.enable()
    secret, msg, corr, idem = "fu1-sensitive-7f3a", "fu1 onboarding note", "fu1|corr-1", "fu1-idem-1"
    other = "fu2-keep-9c1d"
    r1 = e.ledger.commit(Changeset(actor="audit:followup", actor_type="ingest", message=msg,
                                   source={"tenant_ref": "fu1-src"}, correlation_id=corr, idempotency_key=idem)
                         .create_node("fu1|x", labels=["FU1"], properties={"secret": secret}))
    r2 = e.ledger.commit(Changeset(actor="audit:followup", actor_type="ingest", message="fu2 note")
                         .create_node("fu2|y", labels=["FU2"], properties={"keep": other}))
    tokens = ["fu1|x", secret, msg, corr, idem, "fu1-src"]
    stamp = int(time.time())
    pre = str(ARCH / f"ivg_snapshot_{stamp}.snapshot")          # the name POST /admin/snapshot would use
    save_pre = e.save_snapshot(pre)
    erased = e.delete_nodes_by_prefix("fu1|")
    mid = str(ARCH / f"ivg_snapshot_{stamp + 1}.snapshot")
    e.save_snapshot(mid)
    rec = e.ledger.redact(None, prefix="fu1")
    post = str(ARCH / f"ivg_snapshot_{stamp + 2}.snapshot")
    e.save_snapshot(post)
    scan_after_redaction = scan_ledger(c, tokens)
    content_after_redaction = content_rows(c, "fu1|")
    verify_after = str(e.ledger.verify().result)
    archives = {"pre_erase": scan_archive(pre, tokens), "after_erase_before_redaction": scan_archive(mid, tokens),
                "after_redaction": scan_archive(post, tokens)}
    modes = {k: oct(os.stat(p).st_mode & 0o777) for k, p in (("pre", pre), ("mid", mid), ("post", post))}

    # R-10: the stored digest of the target, read back through the public history() reader (no marker check)
    hist = e.ledger.history(limit=100)
    red_rev = [x for x in hist.revisions if x.kind == "redaction"] if hasattr(hist, "revisions") else []
    stored_digest = (red_rev[0].source or {}).get("target_sha256") if red_rev else None
    sql_source = c.sql("SELECT source FROM Graph_KG.ledger_revisions WHERE kind = 'redaction'")
    candidates = [f"t{i:04d}" for i in range(5000)] + ["acme", "fu2", "fu1", "globex", "initech"]

    def td(graph, match):
        return hashlib.sha256((graph + "\x00" + match).encode("utf-8")).hexdigest()
    confirmed = [cand for cand in candidates if td("", cand + "|") == stored_digest]
    objectscript_digest = str(c.call("Graph.KG.LedgerRedact", "TargetDigest", "", "fu1|"))

    # restore the pre-erase archive (replacing restore, the default)
    restore = err(lambda: {k: v for k, v in e.restore_snapshot(pre).items() if k != "failed_rows"})
    content_after_restore = content_rows(c, "fu1|")
    scan_after_restore = scan_ledger(c, tokens)
    props_back = c.sql("SELECT s, \"key\", val FROM Graph_KG.rdf_props WHERE s = 'fu1|x'")
    rev_row = c.sql("SELECT seq, message, correlation_id, idempotency_key FROM Graph_KG.ledger_revisions WHERE seq = ?",
                    r1.revision.seq)
    reset(c)
    sc001_after_redaction_zero = all(v["global_node_count"] == 0 and v["ledger_revisions"] == 0
                                     for v in scan_after_redaction.values())
    pre_holds = {t: sum(v.values()) for t, v in archives["pre_erase"].items()}
    mid_holds = {t: sum(v.values()) for t, v in archives["after_erase_before_redaction"].items()}
    post_holds = {t: sum(v.values()) for t, v in archives["after_redaction"].items()}
    return {
        "observes": "R-01(a), R-10", "tenant_tokens": tokens,
        "commits": {"tenant": r1.revision.seq, "other": r2.revision.seq},
        "save_pre_result": {k: save_pre.get(k) for k in ("path", "globals", "tables")} if isinstance(save_pre, dict) else str(save_pre)[:300],
        "erased_nodes": erased, "receipt": receipt_dict(rec),
        "sc001_scan_after_redaction": scan_after_redaction, "sc001_zero_after_redaction": sc001_after_redaction_zero,
        "content_after_redaction": content_after_redaction, "verify_after_redaction": verify_after,
        "archive_token_hits_by_member": archives,
        "archive_token_totals": {"pre_erase": pre_holds, "after_erase_before_redaction": mid_holds,
                                 "after_redaction": post_holds},
        "archive_file_modes_this_process_umask": modes,
        "receipt_names_snapshots": any("snapshot" in x.lower() or "archive" in x.lower() for x in rec.out_of_reach),
        "restore_pre_erase_archive": restore, "content_after_restore": content_after_restore,
        "props_after_restore": props_back, "revision_row_after_restore": rev_row,
        "sc001_scan_after_restore": scan_after_restore,
        "r10": {"stored_digest_history": stored_digest, "stored_source_sql": sql_source,
                "objectscript_TargetDigest_fu1": objectscript_digest,
                "python_sha256_of_NUL_fu1|": td("", "fu1|"), "candidates_tried": len(candidates),
                "confirmed_candidates": confirmed},
        "verdict": {
            "sc001_holds_in_ledger_after_redaction": sc001_after_redaction_zero,
            "pre_archive_holds_tenant": all(pre_holds[t] > 0 for t in ("fu1|x", secret)),
            "mid_archive_holds_tenant_history": mid_holds[secret] > 0 and mid_holds[msg] > 0,
            "post_archive_clean": all(v == 0 for v in post_holds.values()),
            "receipt_names_snapshots": any("snapshot" in x.lower() for x in rec.out_of_reach),
            "restore_brings_content_back": content_after_restore["nodes"] > 0,
            "restore_brings_history_back": scan_after_restore[secret]["global_node_count"] > 0,
            "guessed_tenant_confirmed_from_digest": confirmed == ["fu1"],
        },
    }


# ------------------------------------------------------------------------------------------------- R-03

def check_r03(c: Conn) -> dict:
    """A writer that keeps the target live keeps a redaction open; while it is open every tenant is blocked."""
    reset(c)
    e = eng(c)
    e.ledger.enable()
    revs = {}
    for t, n in (("fa3", 3), ("fb3", 2), ("fc3", 2)):
        revs[t] = []
        for i in range(n):
            r = e.ledger.commit(Changeset(actor="audit:followup", actor_type="ingest", message=f"{t} {i}")
                                .create_node(f"{t}|n{i}", labels=["T"], properties={"secret": f"{t}-s{i}"}))
            revs[t].append(r.revision.revision_id)
    e.delete_nodes_by_prefix("fa3|")
    e.delete_nodes_by_prefix("fc3|")
    c.conn.commit()
    steps = {}
    # 1. a bounded run of tenant A: one batch of one record, marker set
    steps["1_bounded_run"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="fa3", batch_size=1, max_batches=1)))
    steps["1_marker"] = marker(c)
    # 2. a ledger-bypassing writer (engine.create_node, non-strict ledger: no marker check anywhere on this path)
    steps["2_bypass_write"] = err(lambda: e.create_node("fa3|zombie", labels=["Z"], properties={"secret": "zombie"}))
    c.conn.commit()
    steps["2_a_live_rows"] = content_rows(c, "fa3|")
    steps["2_ledger_commit_into_A_refused"] = err(lambda: e.ledger.commit(
        Changeset(actor="audit:followup", actor_type="ingest").create_node("fa3|via-ledger")).revision.seq)
    # 3. run it again (the documented way to finish it): refused at the entry liveness check, marker kept
    steps["3_rerun"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="fa3")))
    steps["3_marker"] = marker(c)
    # 4. Final's own refusal: erase, start the run while a second connection holds the head lock, write A's
    #    content through the bypass path during the wait, release; the batches finish and Final refuses.
    e.delete_nodes_by_prefix("fa3|")
    c.conn.commit()
    c2 = Conn(NS)
    try:
        e2 = eng(c2)
        c2.o.lock("", 5, "^IVG.Ledger", "head")
        box = {}

        def run():
            box["r"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="fa3")))
        th = threading.Thread(target=run)
        th.start()
        time.sleep(3.0)
        box["write_during_wait"] = err(lambda: e2.create_node("fa3|zombie2", labels=["Z"], properties={"secret": "z2"}))
        c2.conn.commit()
        c2.o.unlock("", "^IVG.Ledger", "head")
        th.join(60)
        steps["4_final_refusal"] = box
        steps["4_marker"] = marker(c)
        steps["4_records_left_untombstoned_A"] = sum(
            1 for seq, _ in c.o.iterator("^IVG.Ledger", "rec").items()
            for o_, _ in c.o.iterator("^IVG.Ledger", "rec", seq).items()
            if str(c.o.getIRISList("^IVG.Ledger", "rec", seq, o_).get(1)) != "redacted"
            and str(c.o.getIRISList("^IVG.Ledger", "rec", seq, o_).get(3) or "").startswith("fa3|"))
    finally:
        c2.close()
    # 5. what every other tenant sees while the marker exists
    b_rev = revs["fb3"][0]
    steps["5_tenant_B_get_revision"] = err(lambda: len(e.ledger.get_revision(b_rev).records))
    steps["5_tenant_B_diff"] = err(lambda: str(e.ledger.diff(revs["fb3"][0], revs["fb3"][1]))[:200])
    steps["5_reconstruct_head"] = err(lambda: str(type(e.ledger.reconstruct(e.ledger.head().revision_id))))
    steps["5_verify"] = err(lambda: str(e.ledger.verify().result))
    steps["5_redact_tenant_C"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="fc3")))
    steps["5_tenant_B_commit"] = err(lambda: e.ledger.commit(
        Changeset(actor="audit:followup", actor_type="ingest").create_node("fb3|later")).revision.seq)
    steps["5_history_not_refused"] = err(lambda: len(e.ledger.history(limit=100).revisions))
    # 6. recovery needs every writer of A to stop: erase again, run again
    e.delete_nodes_by_prefix("fa3|")
    c.conn.commit()
    steps["6_rerun_after_erase"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="fa3")))
    steps["6_marker"] = marker(c)
    steps["6_tenant_B_get_revision"] = err(lambda: len(e.ledger.get_revision(b_rev).records))
    reset(c)
    f = steps["4_final_refusal"].get("r", {})
    return {
        "observes": "R-03", "steps": steps,
        "verdict": {
            "bounded_run_left_marker": bool(steps["1_marker"].get("in_progress")),
            "bypass_write_accepted_while_marked": steps["2_bypass_write"]["ok"],
            "rerun_refused_target_live": (not steps["3_rerun"]["ok"]) and "live" in steps["3_rerun"].get("error", ""),
            "final_refused_target_live": (not f.get("ok", True)) and "became live again" in f.get("error", ""),
            "marker_persists_after_refusals": bool(steps["3_marker"].get("in_progress"))
                                              and bool(steps["4_marker"].get("in_progress")),
            "tenant_B_read_refused": not steps["5_tenant_B_get_revision"]["ok"],
            "verify_reports_in_progress": steps["5_verify"].get("value") == "redaction_in_progress",
            "other_redaction_refused": not steps["5_redact_tenant_C"]["ok"],
            "recovers_once_writers_stop": bool(steps["6_rerun_after_erase"].get("ok"))
                                          and not steps["6_marker"].get("in_progress"),
        },
    }


# ------------------------------------------------------------------------------------------------- R-04

def check_r04(c: Conn) -> dict:
    """Temporal-only edges (ADR-0015) are live content LiveRows never counts."""
    reset(c)
    e = eng(c)
    e.ledger.enable()
    ts = 1_760_000_000
    out = {}
    # control: a structural (default) temporal predicate in its own graph
    cs = Changeset(actor="audit:followup", actor_type="ingest", message="fq ctl")
    cs.create_temporal_edge("fqc|s", "FQ_STRUCT", "fqc|t", ts=ts, weight=1.0, graph="fqctl")
    e.ledger.commit(cs)
    out["control_rows_in_graph"] = c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'fqctl'")[0][0]
    out["control_redact_unerased"] = err(lambda: receipt_dict(e.ledger.redact("fqctl")))
    e.erase_graph("fqctl")  # the control's structural rows would otherwise make every later verify() diverge
    c.conn.commit()
    out["control_redact_after_erase"] = err(lambda: receipt_dict(e.ledger.redact("fqctl"))["complete"])
    out["verify_before_cases"] = str(e.ledger.verify().result)
    # case G: whole-graph target whose only content is a temporal-only edge, not erased at all
    e.set_temporal_structural("FQ_OBS", False, graph="fq4g")
    cs = Changeset(actor="audit:followup", actor_type="ingest", message="fq4 obs")
    cs.create_temporal_edge("fq4|s1", "FQ_OBS", "fq4|t1", ts=ts, weight=7.5, graph="fq4g", attrs={"secret": "fq4-secret"})
    rg = e.ledger.commit(cs)
    out["G_content_rows_in_graph"] = {t: c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE COALESCE(graph_id,'') = 'fq4g'")[0][0]
                                      for t in ("nodes", "rdf_edges", "rdf_props", "rdf_labels")}
    out["G_window_before"] = e.get_edges_in_window(source="fq4|s1", predicate="FQ_OBS", start=ts - 10, end=ts + 10,
                                                   graph="fq4g")
    out["G_records_before"] = [r.to_wire() for r in e.ledger.get_revision(rg.revision.revision_id).records]
    out["G_redact_unerased"] = err(lambda: receipt_dict(e.ledger.redact("fq4g")))
    out["G_window_after"] = e.get_edges_in_window(source="fq4|s1", predicate="FQ_OBS", start=ts - 10, end=ts + 10,
                                                  graph="fq4g")
    out["G_records_after"] = [r.to_wire() for r in e.ledger.get_revision(rg.revision.revision_id).records]
    _v = e.ledger.verify()
    out["G_verify_after"] = str(_v.result)
    out["G_verify_differences"] = [str(x)[:200] for x in (_v.differences or [])[:6]]
    # case P: prefix tenant in the default graph, the documented erase-then-redact order
    e.set_temporal_structural("FQ_OBS", False, graph=None)
    cs = Changeset(actor="audit:followup", actor_type="ingest", message="fq5 data").create_node(
        "fq5|n1", labels=["FQ5"], properties={"k": "v"})
    cs.create_temporal_edge("fq5|s1", "FQ_OBS", "fq5|t1", ts=ts, weight=3.0, graph=None, attrs={"secret": "fq5-secret"})
    rp = e.ledger.commit(cs)
    out["P_erase"] = err(lambda: e.delete_nodes_by_prefix("fq5|"))
    c.conn.commit()
    out["P_content_rows_after_erase"] = content_rows(c, "fq5|")
    out["P_window_after_erase"] = e.get_edges_in_window(source="fq5|s1", predicate="FQ_OBS", start=ts - 10,
                                                        end=ts + 10, graph=None)
    out["P_redact"] = err(lambda: receipt_dict(e.ledger.redact(None, prefix="fq5")))
    out["P_window_after_redact"] = e.get_edges_in_window(source="fq5|s1", predicate="FQ_OBS", start=ts - 10,
                                                         end=ts + 10, graph=None)
    out["P_records_after"] = [r.to_wire() for r in e.ledger.get_revision(rp.revision.revision_id).records]
    _v = e.ledger.verify()
    out["P_verify_after"] = str(_v.result)
    out["P_verify_differences"] = [str(x)[:200] for x in (_v.differences or [])[:6]]
    reset(c)
    g_ok = out["G_redact_unerased"]["ok"]
    return {
        "observes": "R-04", **out,
        "verdict": {
            "control_refused_target_live": (not out["control_redact_unerased"]["ok"])
                                           and "live" in out["control_redact_unerased"].get("error", ""),
            "G_no_structural_rows": sum(out["G_content_rows_in_graph"].values()) == 0,
            "G_edge_live_before": len(out["G_window_before"]) > 0,
            "G_redaction_not_refused": g_ok,
            "G_history_tombstoned_while_live": g_ok and len(out["G_window_after"]) > 0
                                               and all(r.get("op") == "redacted" for r in out["G_records_after"]),
            "P_erase_left_temporal_edge": len(out["P_window_after_erase"]) > 0,
            "P_redaction_completed": bool(out["P_redact"].get("ok")) and out["P_redact"]["value"]["complete"],
            "P_history_tombstoned_while_live": len(out["P_window_after_redact"]) > 0
                                               and all(r.get("op") == "redacted" for r in out["P_records_after"]),
            "verify_equal_after": out["G_verify_after"] == "equal" and out["P_verify_after"] == "equal",
        },
    }


CHECKS = {"r01a": check_r01a, "r03": check_r03, "r04": check_r04}


def main() -> int:
    want = sys.argv[1:] or list(CHECKS)
    c = Conn(NS)
    print("engine:", version(c), "pid", c.pid, flush=True)
    try:
        for name in want:
            t0 = time.time()
            try:
                res = CHECKS[name](c)
            except Exception as ex:
                res = {"exception": f"{type(ex).__name__}: {ex}", "traceback": traceback.format_exc()[-4000:]}
                try:
                    reset(c)
                except Exception as ex2:
                    res["reset_error"] = str(ex2)
            res["seconds"] = round(time.time() - t0, 2)
            res["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            res["namespace"] = NS
            (OUT / f"{name}.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
            print(name, json.dumps(res.get("verdict", res.get("exception")), default=str), flush=True)
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
