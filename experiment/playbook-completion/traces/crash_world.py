#!/usr/bin/env python3
"""Integration world: IRIS instance crash during and after a ledger commit (playbook §3.7, §4.3 liveness/recovery).

    bash tools/locks.sh iris python crash_world.py OUT_DIR            # run only while holding the IRIS lock
    python crash_world.py --self-test-oracle

Trial "in-flight": a client process commits one changeset of N relationships (idempotency key K1); while the commit is
running the container is killed with SIGKILL (no clean shutdown), then started again. Trial "acknowledged": the
commit returns, then the container is killed at once and restarted.

Oracle after restart (independent of the product's answer), on the ledger globals and SQL rows:
- FR-047: a revision exists iff its mutations are visible: either all N records and N edge rows of the key, in
  exactly one revision, or none of either;
- the head equals the number of revisions; Graph_KG.ledger_revisions has exactly one row per revision seq;
- every live statement entry has its tuple entry (stmt/tuple bijection);
- verify() reports equal;
- a retry with the same key then leaves exactly one revision with the content (replay or fresh commit);
- acknowledged trial: the content is present after the crash (durability of an acknowledged commit).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from iris_conn import Conn, version  # noqa: E402

NS = "AUDITCORE"
N = 12000   # 36,000 operations with auto-stubbed endpoints; max_ops is 50,000
CONTAINER = os.environ.get("IVG_TEST_CONTAINER", "")
CLIENT = r'''
import sys, json
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from iris_conn import Conn
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.ledger import Changeset
key, n, tag = sys.argv[3], int(sys.argv[4]), sys.argv[5]
c = Conn("AUDITCORE")
print(json.dumps({"pid": c.pid}), flush=True)
cs = Changeset(actor="audit:crash", actor_type="ingest", idempotency_key=key, auto_stub_missing_nodes=True)
for i in range(n):
    cs.create_relationship(f"{tag}a{i}", "R", f"{tag}b{i}", graph="CW")
r = IRISGraphEngine(c.conn, namespace="AUDITCORE", embedding_dimension=4).ledger.commit(cs)
c.conn.commit()
print(json.dumps({"seq": r.revision.seq, "replayed": bool(getattr(r, "replayed", False))}), flush=True)
'''


def client(key, tag, n=N):
    return subprocess.Popen([sys.executable, "-c", CLIENT, str(HERE.parent / "tools"), str(HERE.parents[2]), key, str(n), tag],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def crash_and_restart() -> dict:
    t = time.time()
    k = subprocess.run(["docker", "kill", "-s", "KILL", CONTAINER], capture_output=True, text=True)
    s = subprocess.run(["docker", "start", CONTAINER], capture_output=True, text=True)
    healthy = False
    for _ in range(180):
        h = subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}", CONTAINER], capture_output=True, text=True)
        if h.stdout.strip() == "healthy":
            healthy = True
            break
        time.sleep(2)
    # the superserver may accept connections a little after the health check
    ok = False
    for _ in range(60):
        try:
            c = Conn(NS)
            c.close()
            ok = True
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return {"kill_rc": k.returncode, "start_rc": s.returncode, "healthy": healthy, "connectable": ok,
            "seconds": round(time.time() - t, 1)}


def observe(c: Conn, tag: str) -> dict:
    rows = int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'CW' AND s %STARTSWITH ?", tag)[0][0])
    head = int(c.o.get("^IVG.Ledger", "head") or 0)
    seqs, recs, stmts_bad = set(), 0, 0
    all_seqs = set()
    for seq, _ in c.o.iterator("^IVG.Ledger", "rec").items():
        all_seqs.add(int(seq))
        for ordn, _ in c.o.iterator("^IVG.Ledger", "rec", seq).items():
            lst = c.o.getIRISList("^IVG.Ledger", "rec", seq, ordn)
            if lst.get(1) == "create_rel" and f'"s":"{tag}a' in str(lst.get(6) or ""):
                recs += 1
                seqs.add(int(seq))
    for sid, _ in c.o.iterator("^IVG.Ledger", "stmt").items():
        row = c.o.getIRISList("^IVG.Ledger", "stmt", sid)
        if str(row.get(6) or "") == "":
            g = str(row.get(4) or "")
            key = c.call("Graph.KG.GraphKey", "ForLedger", g)
            if str(c.o.get("^IVG.Ledger", "tuple", row.get(1), row.get(2), row.get(3), key) or "") != str(sid):
                stmts_bad += 1
    revrows = int(c.sql("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")[0][0])
    from iris_vector_graph.engine import IRISGraphEngine
    v = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger.verify()
    return {"edge_rows": rows, "records": recs, "revisions_with_key": sorted(seqs), "head": head,
            "rec_seqs": len(all_seqs), "revision_rows": revrows, "stmt_without_tuple": stmts_bad,
            "verify": str(getattr(v, "result", v))}


def oracle(o: dict, n: int, must_have: bool = False) -> list:
    bad = []
    all_or_none = (o["records"] == n and o["edge_rows"] == n and len(o["revisions_with_key"]) == 1) or \
                  (o["records"] == 0 and o["edge_rows"] == 0)
    if not all_or_none:
        bad.append(f"FR-047 partial: records {o['records']}, rows {o['edge_rows']}, revisions {o['revisions_with_key']}")
    if must_have and o["records"] != n:
        bad.append("acknowledged commit lost")
    if o["revision_rows"] != o["head"]:
        bad.append(f"revision rows {o['revision_rows']} != head {o['head']}")
    if o["stmt_without_tuple"]:
        bad.append(f"{o['stmt_without_tuple']} live statements without tuple")
    if o["verify"] != "equal":
        bad.append(f"verify {o['verify']}")
    return bad


def trial(name: str, key: str, tag: str, crash_after: float, wait_ack: bool) -> dict:
    p = client(key, tag)
    first = json.loads(p.stdout.readline() or "{}")
    ack = None
    time.sleep(0.5 if not wait_ack else 0)
    if wait_ack:
        line = p.stdout.readline()
        ack = json.loads(line) if line.startswith("{") else None
    else:
        time.sleep(crash_after)
    still_running = p.poll() is None
    restart = crash_and_restart()
    p.kill()
    p.wait(30)
    c = Conn(NS)
    after = observe(c, tag)
    c.close()
    r = client(key, tag)
    out, err = r.communicate(timeout=1800)
    retry = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    if not retry or "seq" not in retry[-1]:
        retry.append({"error": err[-600:]})
    c = Conn(NS)
    final = observe(c, tag)
    c.close()
    return {"trial": name, "client_pid": first.get("pid"), "acknowledged": ack, "commit_running_at_crash": still_running,
            "restart": restart, "after_crash": after, "violations_after_crash": oracle(after, N, must_have=bool(ack)),
            "retry": retry[-1] if retry else {"error": err[-300:]}, "after_retry": final,
            "violations_after_retry": oracle(final, N, must_have=True)}


def main() -> int:
    if "--self-test-oracle" in sys.argv:
        base = {"edge_rows": N, "records": N, "revisions_with_key": [3], "head": 3, "rec_seqs": 3, "revision_rows": 3,
                "stmt_without_tuple": 0, "verify": "equal"}
        partial = oracle({**base, "edge_rows": N // 2}, N)
        lost = oracle({**base, "edge_rows": 0, "records": 0, "revisions_with_key": []}, N, must_have=True)
        head = oracle({**base, "revision_rows": 2}, N)
        good = oracle(base, N, must_have=True)
        ok = bool(partial) and bool(lost) and bool(head) and not good
        print("oracle self-test", "PASS" if ok else "FAIL", partial, lost, head, good)
        return 0 if ok else 1
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    from iris_vector_graph.engine import IRISGraphEngine
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger.enable()
    c.conn.commit()
    c.close()
    results = [trial("in-flight", "crash-1", "c1_", 2.0, False),
               trial("acknowledged", "crash-2", "c2_", 0.0, True)]
    (out / "results.json").write_text(json.dumps(results, indent=1))
    for r in results:
        print(json.dumps({k: r[k] for k in ("trial", "commit_running_at_crash", "restart", "violations_after_crash",
                                             "retry", "violations_after_retry")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
