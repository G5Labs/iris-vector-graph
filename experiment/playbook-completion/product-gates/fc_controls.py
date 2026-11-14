#!/usr/bin/env python3
"""Negative controls for five failure scenarios that had none (FAILURE-CONTROLS.md S5b, S13, S15, S16, S17).

    source experiment/playbook-completion/environment.sh
    bash experiment/playbook-completion/tools/locks.sh iris python \
        experiment/playbook-completion/product-gates/fc_controls.py s5b|s13|s15|s16|s17 OUT_DIR

Each scenario keeps the oracle of its original run and applies it, unchanged, to two live arms in namespace AUDITIA,
built with the product's own calls from an empty state (Graph.KG.Eraser.EraseAll + Graph.KG.Ledger.PurgeAll):
the arm where the defect's precondition is ABSENT (the oracle must pass) and the arm where it is PRESENT (the oracle
must flag). A control passes when both hold. Nothing is compiled, no product file is touched; at most 5 connections.

  s5b  F-1102 (b-11-live-f1102-locktimeout). Oracle: a rejection counter bumped by process B moves by exactly one.
       absent: the stats row is free. present: process A holds a caller transaction whose nested ledger commit saved
       the stats row, for 15 s, while B bumps.
  s13  F-C1307 (fu-r03-marker-held-open). Oracle: after an interrupted bounded redaction, the documented recovery (run
       it again) releases the marker, another tenant's revision is readable and verify() is equal.
       absent: no writer touches the target. present: a ledger-bypassing create_node writes into the target while the
       marker is set (accepted on a non-strict ledger).
  s15  F-C0801 (b-08-live-fc0801-rollback-nkg). Oracle SYS-I8/CYP-I6.4: after a Cypher write query, the interned
       snapshot's counters ^NKG(-3,src) and ^NKG("$meta","edgeCount") move with the rdf_edges rows, or ^NKG is marked
       stale. absent: the query commits. present: its second CREATE fails and the query rolls back.
  s16  killed bulk load (breadth-a-live-03-bulk-killed-client, F-0305). Oracle: one bulk_create_nodes call is all or
       nothing. present: the server-loader path (capabilities read, as the original probe did), a two-chunk call
       (1,000 unlabelled + 1,000 labelled nodes) killed while chunk 2 waits on a table lock on rdf_labels. absent (a):
       the same call not killed; absent (b): the batch-SQL path (fresh engine, one cursor transaction) killed alike.
  s17  max_ops refusal (live-maxops-60000-refused). Oracle: the changeset is refused (ChangesetTooLargeError) and
       nothing of it is applied (no rows, head unchanged). precondition of the refusal present: 50,001 operations
       (the oracle passes); absent: 50,000 operations, the limit itself (the oracle flags: the changeset is applied).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from iris_conn import Conn, version  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITIA"
L = "Graph.KG.Ledger"


def eng(c: Conn, **kw) -> IRISGraphEngine:
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine(c.conn, namespace=NS, **kw)


def reset(c: Conn) -> None:
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call(L, "PurgeAll")
    c.conn.commit()


def err(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as e:  # noqa: BLE001 - the outcome is data
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)[:500]}


def stats(c: Conn) -> dict:
    k = ["commits_ok", "rej_stale_head", "rej_size_limit", "rej_lock_timeout"]
    rows = c.sql("SELECT commits_ok, rej_stale_head, rej_size_limit, rej_lock_timeout FROM Graph_KG.ledger_stats")
    return dict(zip(k, [int(x or 0) for x in rows[0]])) if rows else {x: 0 for x in k}


def control(arms: dict, oracle_name: str) -> dict:
    """arms: {name: {"precondition": "absent"|"present", "violations": [...]}}"""
    ok_absent = all(not a["violations"] for a in arms.values() if a["precondition"] == "absent")
    ok_present = all(a["violations"] for a in arms.values() if a["precondition"] == "present")
    return {"oracle": oracle_name, "arms": arms, "passes_when_absent": ok_absent, "flags_when_present": ok_present,
            "control_result": "pass" if ok_absent and ok_present else "fail"}


# ------------------------------------------------------------------------------------------------- S5b (F-1102)
def oracle_s5b(before: dict, after: dict) -> list:
    n = after["rej_stale_head"] - before["rej_stale_head"]
    return [] if n == 1 else [f"rejection counter rej_stale_head moved by {n}, not 1"]


def s5b(c: Conn) -> dict:
    reset(c)
    e = eng(c)
    e.create_node("pgs5|hold", labels=["PG"])
    c.conn.commit()
    e.ledger.enable()
    wa, wb = Conn(NS), Conn(NS)
    arms = {}
    try:
        # absent: nobody holds the stats row
        b0 = stats(c)
        t = time.time()
        st = err(lambda: str(wb.call(L, "Count", "rej_stale_head")))
        b1 = stats(c)
        arms["stats-row-free"] = {"precondition": "absent", "b_status": st, "b_seconds": round(time.time() - t, 3),
                                  "before": b0, "after": b1, "violations": oracle_s5b(b0, b1)}
        # present: A's caller transaction holds the stats row (its nested commit saved it) for 15 s
        ea = eng(wa)
        cur = wa.conn.cursor()
        cur.execute("START TRANSACTION")
        r = ea.ledger.commit(Changeset(actor="audit:pg", actor_type="service").set_property("pgs5|hold", "k", "v"))
        b0 = stats(c)
        res = {}

        def bump():
            t0 = time.time()
            res["status"] = err(lambda: str(wb.call(L, "Count", "rej_stale_head")))
            res["seconds"] = round(time.time() - t0, 3)
        th = threading.Thread(target=bump)
        th.start()
        time.sleep(15)
        cur.execute("ROLLBACK")
        cur.close()
        th.join(120)
        b1 = stats(c)
        arms["stats-row-held-by-caller-transaction"] = {
            "precondition": "present", "a_commit_seq_in_txn": r.revision.seq, "b_status": res.get("status"),
            "b_seconds": res.get("seconds"), "before": b0, "after_a_rollback": b1, "violations": oracle_s5b(b0, b1)}
    finally:
        wa.close()
        wb.close()
    reset(c)
    return control(arms, "F-1102 oracle: a rejection counter bumped by another process moves by exactly one")


# ------------------------------------------------------------------------------------------------- S13 (F-C1307)
def marker(c: Conn) -> dict:
    return json.loads(str(c.call("Graph.KG.LedgerRedact", "InProgress")))


def oracle_s13(after: dict) -> list:
    bad = []
    if after["marker"].get("in_progress"):
        bad.append("marker kept after the documented recovery (run again)")
    if not after["tenant_b_get_revision"]["ok"]:
        bad.append(f"tenant B's revision refused: {after['tenant_b_get_revision'].get('error_type')}")
    if after["verify"].get("value") != "equal":
        bad.append(f"verify {after['verify']}")
    return bad


def s13_world(c: Conn, bypass: bool) -> dict:
    reset(c)
    e = eng(c)
    e.ledger.enable()
    revs = {}
    for t, n in (("pga", 3), ("pgb", 2)):
        revs[t] = [e.ledger.commit(Changeset(actor="audit:pg", actor_type="ingest", message=f"{t} {i}")
                                   .create_node(f"{t}|n{i}", labels=["T"], properties={"secret": f"{t}-s{i}"}))
                   .revision.revision_id for i in range(n)]
    e.delete_nodes_by_prefix("pga|")
    c.conn.commit()
    w = {"bounded_run": err(lambda: e.ledger.redact(None, prefix="pga", batch_size=1, max_batches=1).complete)}
    w["marker_after_bounded_run"] = marker(c)
    if bypass:
        w["bypass_write"] = err(lambda: e.create_node("pga|zombie", labels=["Z"], properties={"secret": "zombie"}))
        c.conn.commit()
    w["recovery_rerun"] = err(lambda: e.ledger.redact(None, prefix="pga").complete)
    after = {"marker": marker(c), "tenant_b_get_revision": err(lambda: len(e.ledger.get_revision(revs["pgb"][0]).records)),
             "verify": err(lambda: str(e.ledger.verify().result))}
    w["after_recovery"] = after
    w["violations"] = oracle_s13(after)
    if bypass:   # leave AUDITIA clean: the recovery F-C1307 records (erase again, run again)
        e.delete_nodes_by_prefix("pga|")
        c.conn.commit()
        w["cleanup_rerun_after_erase"] = err(lambda: e.ledger.redact(None, prefix="pga").complete)
        w["cleanup_marker"] = marker(c)
    return w


def s13(c: Conn) -> dict:
    arms = {"no-writer-on-the-target": dict(s13_world(c, bypass=False), precondition="absent"),
            "bypass-writer-on-the-target": dict(s13_world(c, bypass=True), precondition="present")}
    reset(c)
    return control(arms, "F-C1307 oracle: the documented recovery releases the marker; other tenants readable; verify equal")


# ------------------------------------------------------------------------------------------------- S15 (F-C0801)
def nkg_state(c: Conn, src: str) -> dict:
    o = c.o
    si = o.get("NKG", "$NI", src) if o.isDefined("NKG", "$NI", src) else None
    deg = o.get("NKG", -3, si) if si is not None and o.isDefined("NKG", -3, si) % 10 == 1 else None
    return {"src_idx": si, "deg": int(deg) if deg is not None else None,
            "edgeCount": int(o.get("NKG", "$meta", "edgeCount")) if o.isDefined("NKG", "$meta", "edgeCount") else None,
            "stale": o.get("NKG", "$meta", "stale") if o.isDefined("NKG", "$meta", "stale") else None,
            "rows_out_of_src": int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ?", src)[0][0]),
            "rows_total": int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges")[0][0])}


def oracle_s15(b: dict, a: dict) -> list:
    if a["stale"]:
        return []
    bad = []
    if b["deg"] is None or a["deg"] is None:
        bad.append("source not interned in ^NKG (precondition of the check missing)")
    elif a["deg"] - b["deg"] != a["rows_out_of_src"] - b["rows_out_of_src"]:
        bad.append(f"^NKG(-3,src) moved {a['deg'] - b['deg']}, rows out of src moved "
                   f"{a['rows_out_of_src'] - b['rows_out_of_src']}, no stale mark")
    if b["edgeCount"] is not None and a["edgeCount"] - b["edgeCount"] != a["rows_total"] - b["rows_total"]:
        bad.append(f"edgeCount moved {a['edgeCount'] - b['edgeCount']}, rows moved {a['rows_total'] - b['rows_total']}")
    return bad


def s15(c: Conn) -> dict:
    reset(c)
    e = eng(c, native_cypher=False)

    def run(q):
        return err(lambda: (lambda r: getattr(r, "error", None))(e.execute_cypher(q)))
    setup = [run("CREATE (:PGRN {id:'pg_r1'}), (:PGRN {id:'pg_r2'}), (:PGRN {id:'pg_r3'})"),
             run("MATCH (a:PGRN {id:'pg_r1'}), (b:PGRN {id:'pg_r3'}) CREATE (a)-[:PGOLD]->(b)"),
             run("CREATE (a:PGJ {id:'pg_j5'})-[:PGT]->(b:PGJ {id:'pg_j6'})")]
    sync = err(lambda: str(e.sync())[:200])
    arms = {}
    b = nkg_state(c, "pg_r1")
    q = "MATCH (a:PGRN {id:'pg_r1'}), (b:PGRN {id:'pg_r2'}) CREATE (a)-[:PGNEW]->(b)"
    out = run(q)
    a = nkg_state(c, "pg_r1")
    arms["write-query-commits"] = {"precondition": "absent", "query": q, "result": out, "before": b, "after": a,
                                   "violations": oracle_s15(b, a)}
    b = nkg_state(c, "pg_r1")
    q = ("MATCH (a:PGRN {id:'pg_r1'}), (b:PGRN {id:'pg_r2'}) CREATE (a)-[:PGNEW2]->(b) "
         "CREATE (c:PGJ {id:'pg_j5'})-[:PGT]->(d:PGJ {id:'pg_j6'})")
    out = run(q)
    a = nkg_state(c, "pg_r1")
    arms["write-query-rolls-back"] = {"precondition": "present", "query": q, "result": out, "before": b, "after": a,
                                      "violations": oracle_s15(b, a)}
    res = control(arms, "F-C0801 oracle (SYS-I8, CYP-I6.4): ^NKG counters move with the edge rows or ^NKG says stale")
    res["setup"] = setup
    res["sync"] = sync
    reset(c)
    res["resync_after_reset"] = err(lambda: str(eng(c).sync())[:200])
    return res


# ------------------------------------------------------------------------------------------------- S16 (bulk load)
CLIENT16 = r'''
import sys, json, os
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from iris_conn import Conn
Conn("AUDITIA").close()                         # identity check of the dedicated container
import iris
from iris_vector_graph.engine import IRISGraphEngine
e = IRISGraphEngine.from_connect("127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace="AUDITIA",
                                 username="_SYSTEM", password="SYS", embedding_dimension=4)
pids = {str(iris.createIRIS(e.conn).classMethodValue("%SYSTEM.SYS", "ProcessID"))}
pids.add(str(e._iris_obj().classMethodValue("%SYSTEM.SYS", "ProcessID")))
# "loader": read the capabilities first, as the original probe did: a batch with no graph keys then goes to the
# server loader in 1,000-node chunks (nodes_edges.py:1707-1716); "sql": a fresh engine takes the batch-SQL path
deployed = bool(e.capabilities.objectscript_deployed) if sys.argv[4] == "loader" else None
print(json.dumps({"pids": sorted(pids), "path": sys.argv[4], "objectscript_deployed": deployed}), flush=True)
sys.stdin.readline()                            # the harness takes its table lock, then says go
nodes = json.loads(sys.argv[3])
r = e.bulk_create_nodes(nodes, disable_indexes=False)
print(json.dumps({"returned": len(r)}), flush=True)
'''


def counts16(c: Conn, prefix: str) -> dict:
    return {t: int(c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE graph_id = '' AND {col} %STARTSWITH ?", prefix)[0][0])
            for t, col in (("nodes", "node_id"), ("rdf_props", "s"), ("rdf_labels", "s"))}


def oracle_s16(cnt: dict, n_nodes: int, n_labelled: int) -> list:
    full = cnt == {"nodes": n_nodes, "rdf_props": n_nodes, "rdf_labels": n_labelled}
    none = cnt == {"nodes": 0, "rdf_props": 0, "rdf_labels": 0}
    return [] if full or none else [f"partial bulk write: {cnt} (want {n_nodes} nodes, {n_nodes} props, "
                                    f"{n_labelled} labels, or nothing)"]


def s16_arm(c: Conn, prefix: str, unlabelled: int, labelled: int, kill: bool, path: str) -> dict:
    nodes = [{"id": f"{prefix}_{i:04d}"} for i in range(unlabelled)] + \
            [{"id": f"{prefix}_{i:04d}", "labels": ["PGBK"]} for i in range(unlabelled, unlabelled + labelled)]
    p = subprocess.Popen([sys.executable, "-c", CLIENT16, str(HERE.parent / "tools"), str(HERE.parents[2]),
                          json.dumps(nodes), path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    first = json.loads(p.stdout.readline() or "{}")
    pids = first.get("pids", [])
    blocker = Conn(NS)
    blocker.o.tStart()
    blocker.sql("LOCK TABLE Graph_KG.rdf_labels IN EXCLUSIVE MODE")
    p.stdin.write("go\n")
    p.stdin.flush()
    time.sleep(4)
    w = {"client_pids": pids, "path": first.get("path"), "objectscript_deployed": first.get("objectscript_deployed"),
         "running_at_4s": p.poll() is None,
         "visible_mid_call": counts16(c, prefix + "_")}
    exited = None
    if kill:
        os.kill(p.pid, signal.SIGKILL)
        p.wait(30)
        # keep the table lock until the dead client's server processes are gone, so a waiting chunk cannot commit
        # after the kill; a process still waiting after 20 s (its lock wait has no timeout here) is terminated by its
        # recorded pid (the client's own server process), which rolls its open transaction back
        t0 = time.time()
        while time.time() - t0 < 20 and any(int(c.call("%SYS.ProcessQuery", "%ExistsId", x) or 0) for x in pids):
            time.sleep(0.2)
        alive = [x for x in pids if int(c.call("%SYS.ProcessQuery", "%ExistsId", x) or 0)]
        w["terminated_after_20s"] = {x: int(c.call("%SYSTEM.Process", "Terminate", x) or 0) for x in alive}
        exited = round(time.time() - t0, 1)
    blocker.sql("UNLOCK TABLE Graph_KG.rdf_labels IN EXCLUSIVE MODE")
    blocker.o.tRollback()
    blocker.close()
    out, errt = p.communicate(timeout=300) if p.poll() is None else (p.stdout.read(), p.stderr.read())
    w["client_lines"] = [ln for ln in out.splitlines() if ln.startswith("{")]
    w["client_stderr_tail"] = errt[-300:]
    w["seconds_kill_to_server_exit"] = exited
    t0 = time.time()
    while time.time() - t0 < 60 and any(int(c.call("%SYS.ProcessQuery", "%ExistsId", x) or 0) for x in pids):
        time.sleep(0.2)
    w["after"] = counts16(c, prefix + "_")
    w["violations"] = oracle_s16(w["after"], unlabelled + labelled, labelled)
    for t, col in (("rdf_props", "s"), ("rdf_labels", "s"), ("nodes", "node_id")):
        c.sql(f"DELETE FROM Graph_KG.{t} WHERE graph_id = '' AND {col} %STARTSWITH ?", prefix + "_")
    return w


def s16(c: Conn) -> dict:
    reset(c)
    arms = {"loader-two-chunks-not-killed": dict(s16_arm(c, "pgbk1", 1000, 1000, False, "loader"), precondition="absent"),
            "sql-path-two-chunks-killed-while-waiting": dict(s16_arm(c, "pgbk2", 1000, 1000, True, "sql"),
                                                             precondition="absent"),
            "loader-two-chunks-killed-in-chunk-2": dict(s16_arm(c, "pgbk3", 1000, 1000, True, "loader"),
                                                        precondition="present")}
    reset(c)
    return control(arms, "F-0305 / killed bulk load oracle: one bulk_create_nodes call is all or nothing")


# ------------------------------------------------------------------------------------------------- S17 (max_ops)
def oracle_s17(w: dict) -> list:
    bad = []
    if w["commit"]["ok"] or w["commit"].get("error_type") != "ChangesetTooLargeError":
        bad.append(f"not refused with ChangesetTooLargeError: {str(w['commit'])[:160]}")
    if w["rows_after"]:
        bad.append(f"{w['rows_after']} node rows of the changeset applied")
    if w["head_after"] != w["head_before"]:
        bad.append(f"head moved {w['head_before']} -> {w['head_after']}")
    return bad


def s17_arm(c: Conn, tag: str, n_ops: int) -> dict:
    e = eng(c)
    cs = Changeset(actor="audit:pg", actor_type="ingest", idempotency_key=f"pg-s17-{tag}-{int(time.time())}")
    for i in range(n_ops):
        cs.create_node(f"{tag}{i}")
    h0 = int(c.o.get("^IVG.Ledger", "head") or 0)
    s0 = stats(c)
    t = time.time()
    w = {"operations": n_ops, "head_before": h0}
    w["commit"] = err(lambda: e.ledger.commit(cs).revision.seq)
    w["seconds"] = round(time.time() - t, 2)
    w["head_after"] = int(c.o.get("^IVG.Ledger", "head") or 0)
    w["rows_after"] = int(c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?", tag)[0][0])
    s1 = stats(c)
    w["rej_size_limit_moved"] = s1["rej_size_limit"] - s0["rej_size_limit"]
    w["violations"] = oracle_s17(w)
    return w


def s17(c: Conn) -> dict:
    reset(c)
    eng(c).ledger.enable()
    w = {"max_ops": json.loads(str(c.call(L, "Meta"))).get("max_ops")}
    arms = {"50001-operations-over-the-limit": dict(s17_arm(c, "pgmxa", 50001), precondition="present"),
            "50000-operations-at-the-limit": dict(s17_arm(c, "pgmxb", 50000), precondition="absent")}
    reset(c)
    # here the refusal is the property, so the oracle must PASS where the refusal's precondition is present and
    # FLAG where it is absent (an applied changeset)
    ok_present = not arms["50001-operations-over-the-limit"]["violations"]
    ok_absent = bool(arms["50000-operations-at-the-limit"]["violations"])
    return {"oracle": "max_ops refusal oracle: refused with ChangesetTooLargeError, nothing applied, head unchanged",
            "meta": w, "arms": arms, "passes_when_over_limit": ok_present, "flags_when_at_limit": ok_absent,
            "control_result": "pass" if ok_present and ok_absent else "fail"}


SCEN = {"s5b": s5b, "s13": s13, "s15": s15, "s16": s16, "s17": s17}


def main() -> int:
    name, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    c = Conn(NS)
    try:
        t = time.time()
        res = {"scenario": name, "engine": version(c), "namespace": NS,
               "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        res.update(SCEN[name](c))
        res["seconds"] = round(time.time() - t, 1)
    finally:
        c.close()
    (out / f"{name}.json").write_text(json.dumps(res, indent=1, default=str))
    summ = {k: v for k, v in res.items() if k not in ("arms", "setup")}
    summ["arms"] = {k: {"precondition": a.get("precondition"), "violations": a.get("violations")}
                    for k, a in res.get("arms", {}).items()}
    print(json.dumps(summ, default=str))
    return 0 if res.get("control_result") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
