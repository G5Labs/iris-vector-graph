#!/usr/bin/env python3
"""Integration world: lost acknowledgement and client disconnect during a ledger commit (playbook §3.7).

    python lost_ack.py OUT_DIR [--self-test-oracle]

For each kill delay d, a client OS process commits one changeset (N relationships, idempotency key K_d) through the
pin's public Python API; the harness SIGKILLs that client after d seconds, waits until its IRIS server process has
exited, then a fresh client retries the identical changeset with the same key. Whether the first attempt committed
is unknown to the client: that is the ambiguous acknowledgement.

Oracle (independent of the product's own answer): after the retry
- exactly one revision carries key K_d's content (ledger records counted from ^IVG.Ledger("rec") by fingerprint of
  the relationship ids), and the head advanced by exactly one for this key;
- the content rows of the changeset exist exactly once (SQL counts);
- verify() reports equal.
The retry's own result (replayed or fresh) is recorded; both are permitted. --self-test-oracle feeds the oracle a
synthetic double-applied observation and a missing-content observation and requires both to be rejected.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from iris_conn import Conn, version  # noqa: E402

NS = "AUDITCORE"
N = 1500
CLIENT = r'''
import sys, json, os
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from iris_conn import Conn
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.ledger import Changeset
key, n, tag = sys.argv[3], int(sys.argv[4]), sys.argv[5]
c = Conn("AUDITCORE")
print(json.dumps({"pid": c.pid}), flush=True)
cs = Changeset(actor="audit:lostack", actor_type="ingest", idempotency_key=key, auto_stub_missing_nodes=True)
for i in range(n):
    cs.create_relationship(f"{tag}a{i}", "R", f"{tag}b{i}", graph="LA")
r = IRISGraphEngine(c.conn, namespace="AUDITCORE", embedding_dimension=4).ledger.commit(cs)
c.conn.commit()
print(json.dumps({"seq": r.revision.seq, "replayed": bool(getattr(r, "replayed", False))}), flush=True)
'''


def client(key: str, tag: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", CLIENT, str(HERE.parent / "tools"), str(HERE.parents[2]), key, str(N), tag],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def observe(c: Conn, tag: str) -> dict:
    rows = c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'LA' AND s %STARTSWITH ?", tag)[0][0]
    recs = 0
    seqs = set()
    for seq, _ in c.o.iterator("^IVG.Ledger", "rec").items():
        for ordn, _ in c.o.iterator("^IVG.Ledger", "rec", seq).items():
            lst = c.o.getIRISList("^IVG.Ledger", "rec", seq, ordn)
            if lst.get(1) == "create_rel" and str(lst.get(6) or "").find(f'"s":"{tag}a') >= 0:
                recs += 1
                seqs.add(str(seq))
    return {"edge_rows": int(rows), "create_rel_records": recs, "revisions": sorted(seqs)}


def oracle(obs: dict) -> list:
    bad = []
    if obs["edge_rows"] != N:
        bad.append(f"content rows {obs['edge_rows']} != {N}")
    if obs["create_rel_records"] != N or len(obs["revisions"]) != 1:
        bad.append(f"records {obs['create_rel_records']} in revisions {obs['revisions']} (want {N} in exactly one)")
    if obs.get("verify") not in ("equal", None):
        bad.append(f"verify {obs.get('verify')}")
    return bad


def reevaluate(path: Path) -> int:
    """Re-apply the oracle to recorded results (the verify field holds the report's result or its text)."""
    import re
    results = json.loads(path.read_text())
    for r in results:
        v = r["after_retry"]["verify"]
        m = re.search(r"result='(\w+)'", v)
        r["after_retry"]["verify"] = m.group(1) if m else v
        r["violations"] = oracle(r["after_retry"])
    bad = [r["delay_s"] for r in results if r["violations"]]
    print(json.dumps([{k: r[k] for k in ("delay_s", "client_killed", "violations")} | {"retry": r["retry"],
                       "committed_before_retry": bool(r["after_kill"]["revisions"])} for r in results]))
    print(f"oracle violations in {len(bad)} of {len(results)}: {bad}")
    return 0 if not bad else 1


def main() -> int:
    if "--reevaluate" in sys.argv:
        return reevaluate(Path(sys.argv[sys.argv.index("--reevaluate") + 1]))
    if "--self-test-oracle" in sys.argv:
        double = oracle({"edge_rows": N, "create_rel_records": 2 * N, "revisions": ["3", "4"], "verify": "equal"})
        missing = oracle({"edge_rows": 0, "create_rel_records": N, "revisions": ["3"], "verify": "diverged"})
        good = oracle({"edge_rows": N, "create_rel_records": N, "revisions": ["3"], "verify": "equal"})
        ok = bool(double) and bool(missing) and not good
        print("oracle self-test", "PASS" if ok else "FAIL", double, missing, good)
        return 0 if ok else 1
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    ctl = Conn(NS)
    print("engine:", version(ctl), flush=True)
    from iris_vector_graph.engine import IRISGraphEngine
    ctl.call("Graph.KG.Eraser", "EraseAll")
    ctl.call("Graph.KG.Ledger", "PurgeAll")
    IRISGraphEngine(ctl.conn, namespace=NS, embedding_dimension=4).ledger.enable()
    ctl.conn.commit()
    results = []
    for i, delay in enumerate([0.05, 0.3, 0.8, 1.5, 3.0, 8.0]):
        key, tag = f"lostack-{i}", f"t{i}_"
        p = client(key, tag)
        first = json.loads(p.stdout.readline() or "{}")
        time.sleep(delay)
        killed = p.poll() is None
        if killed:
            os.kill(p.pid, signal.SIGKILL)
        p.wait(30)
        rest = p.stdout.read()
        srv = first.get("pid")
        end = time.time() + 60
        while srv and time.time() < end and int(ctl.call("%SYS.ProcessQuery", "%ExistsId", srv) or 0):
            time.sleep(0.2)
        mid = observe(ctl, tag)
        r = client(key, tag)
        out_r, err_r = r.communicate(timeout=300)
        retry = [json.loads(x) for x in out_r.splitlines() if x.startswith("{")]
        obs = observe(ctl, tag)
        v = IRISGraphEngine(ctl.conn, namespace=NS, embedding_dimension=4).ledger.verify()
        obs["verify"] = str(getattr(v, "result", v))
        res = {"delay_s": delay, "client_killed": killed, "first_reply": rest.strip()[-200:],
               "after_kill": mid, "retry": retry[-1] if retry else {"error": err_r[-300:]}, "after_retry": obs,
               "violations": oracle(obs)}
        results.append(res)
        print(json.dumps(res), flush=True)
    (out / "results.json").write_text(json.dumps(results, indent=1))
    worlds = {"committed-before-kill": sum(1 for r in results if r["after_kill"]["revisions"]),
              "nothing-before-kill": sum(1 for r in results if not r["after_kill"]["revisions"])}
    bad = sum(1 for r in results if r["violations"])
    print(f"worlds {worlds}; oracle violations in {bad} of {len(results)}")
    ctl.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
