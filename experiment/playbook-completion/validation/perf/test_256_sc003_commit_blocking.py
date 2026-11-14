"""Spec 256 SC-003, measured from the committer's side (validation lane, completion audit).

SC-003: "Redacting a tenant with 100,000 records takes under 60 s on the laptop's enterprise container and blocks
commits for under 1 s at a time (batching)." The upstream test (tests/integration/test_256_ledger_redaction_perf.py)
reads the redaction's own receipt (`max_batch_ms`). This module measures the second half independently: N committer
processes (separate OS processes, each with its own IRIS connection) commit small changesets to tenants outside the
target before, during and after the redaction, and record each commit's wall time. The longest commit that overlaps
the redaction bounds the time a commit was blocked.

Public API only: IRISGraphEngine, ledger.enable / commit (Changeset) / redact / verify, delete_nodes_by_prefix. The
namespace is reset by the upstream fixtures (`iris_connection`, `ledger_reset`, loaded with `-p tests.conftest`).
Each cycle is A (committers alone, before) / B (during the redaction) / A (after): alternating windows on the same
state, repeated per cycle.

Environment: IVG_AUDIT_RECORDS (100000), IVG_AUDIT_CYCLES (3), IVG_AUDIT_COMMITTERS (1), IVG_AUDIT_WINDOW_S (8),
IVG_AUDIT_OUT (JSON path for the measurements).
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import statistics
import time

import pytest

from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.ledger import Changeset

RECORDS = int(os.environ.get("IVG_AUDIT_RECORDS", "100000"))
CYCLES = int(os.environ.get("IVG_AUDIT_CYCLES", "3"))
COMMITTERS = int(os.environ.get("IVG_AUDIT_COMMITTERS", "1"))
WINDOW_S = float(os.environ.get("IVG_AUDIT_WINDOW_S", "8"))
OUT = os.environ.get("IVG_AUDIT_OUT", "")
PER_NODE = 4  # create_node, add_label, two set_prop (as upstream)
PER_COMMIT = 2_500


def _params():
    return {"hostname": "127.0.0.1", "port": int(os.environ["IVG_PORT"]),
            "namespace": os.environ.get("IVG_NAMESPACE", "USER"), "username": "_SYSTEM", "password": "SYS"}


def _committer(params, worker, stop, ready, out):
    """Commit one-node changesets to tenant `oth<worker>` until `stop`; record (t0, t1, outcome) per commit."""
    import iris.dbapi as dbapi

    from tests import conftest as fixtures

    conn = dbapi.connect(**params)
    expected = os.environ["IVG_TEST_CONTAINER"]
    if not fixtures.container_hostname_matches(fixtures.probe_instance_hostname(conn),
                                               fixtures.docker_container_hostname(expected),
                                               fixtures.docker_container_id(expected)):
        out.put((worker, "identity-mismatch", []))
        return
    eng = IRISGraphEngine(conn, embedding_dimension=4)
    rows, k = [], 0
    ready.set()
    while not stop.is_set():
        cs = Changeset(actor="ingest:etl", actor_type="ingest", message=f"oth{worker} {k}")
        cs.upsert_node(f"oth{worker}|n{k}", properties={"v": f"oth{worker}-{k}"})
        t0 = time.monotonic()
        try:
            r = eng.ledger.commit(cs)
            outcome = "ok" if r.revision and not r.replayed else "replayed"
        except Exception as exc:  # recorded, never hidden
            outcome = f"{type(exc).__name__}: {str(exc)[:160]}"
        rows.append((t0, time.monotonic(), outcome))
        k += 1
    conn.close()
    out.put((worker, "done", rows))


def _stats(lat):
    if not lat:
        return {"n": 0}
    s = sorted(lat)
    return {"n": len(s), "max_ms": round(s[-1] * 1000, 1), "p50_ms": round(statistics.median(s) * 1000, 2),
            "p95_ms": round(s[min(len(s) - 1, int(0.95 * len(s)))] * 1000, 2),
            "mean_ms": round(statistics.fmean(s) * 1000, 2)}


@pytest.fixture
def engine(iris_connection, ledger_reset):
    eng = IRISGraphEngine(iris_connection, embedding_dimension=4)
    eng.ledger.enable()
    return eng


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_sc003_commit_blocking_seen_by_concurrent_committers(engine, cycle, capsys):
    led = engine.ledger
    nodes = RECORDS // PER_NODE
    t0 = time.perf_counter()
    for start in range(0, nodes, PER_COMMIT):
        cs = Changeset(actor="ingest:etl", actor_type="ingest", message="big tenant load", correlation_id=f"big|{start}")
        for i in range(start, min(nodes, start + PER_COMMIT)):
            cs.create_node(f"big|n{i}", labels=["BigLabel"], properties={"a": f"big-a-{i}", "b": f"big-b-{i}"})
        led.commit(cs)
    cs = Changeset(actor="ingest:etl", actor_type="ingest", message="small tenant")
    for i in range(1_000):
        cs.create_node(f"small|n{i}", properties={"a": f"small-a-{i}"})
    led.commit(cs)
    build_s = time.perf_counter() - t0
    engine.delete_nodes_by_prefix("big|")

    ctx = mp.get_context("spawn")
    stop, out = ctx.Event(), ctx.Queue()
    readies = [ctx.Event() for _ in range(COMMITTERS)]
    procs = [ctx.Process(target=_committer, args=(_params(), w, stop, readies[w], out)) for w in range(COMMITTERS)]
    for p in procs:
        p.start()
    for e in readies:
        assert e.wait(120), "a committer did not start"
    a_pre = (time.monotonic(), None)
    time.sleep(WINDOW_S)
    b0 = time.monotonic()
    r = led.redact(None, prefix="big")
    b1 = time.monotonic()
    time.sleep(WINDOW_S)
    a_post_end = time.monotonic()
    stop.set()
    results = [out.get(timeout=300) for _ in procs]
    for p in procs:
        p.join(60)
    rows = [row for _, status, rs in results for row in rs]
    assert all(status == "done" for _, status, _ in results), results

    def window(lo, hi):  # commits that overlap [lo, hi]
        return [(c0, c1, o) for c0, c1, o in rows if c1 >= lo and c0 <= hi]

    pre = [c for c in window(a_pre[0], b0) if c[1] < b0]
    during = window(b0, b1)
    post = [c for c in window(b1, a_post_end) if c[0] > b1]
    errors = sorted({o for _, _, o in rows if o not in ("ok", "replayed")})
    ok_commits = sum(1 for _, _, o in rows if o == "ok")

    t2 = time.perf_counter()
    report = led.verify()
    verify_s = time.perf_counter() - t2
    # every successful committer commit is live (multi-process: nothing lost)
    cur = engine.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'oth'")
    live_oth = int(cur.fetchone()[0])
    cur.close()
    # the history is one contiguous single-parent chain (multi-process: no fork, no gap)
    chain, after = [], 0
    while True:
        page = led.history(after_seq=after, limit=1000)
        chain += [(r.seq, r.revision_id, r.parent_id) for r in page.revisions]
        if not page.next_after_seq:
            break
        after = page.next_after_seq
    head_seq = led.head().seq
    contiguous = [s for s, _, _ in chain] == list(range(1, head_seq + 1))
    single_parent = all(cur_[2] == prev[1] for prev, cur_ in zip(chain, chain[1:]))

    m = {
        "cycle": cycle, "committers": COMMITTERS, "records_target": nodes * PER_NODE, "build_s": round(build_s, 1),
        "redact_s": round(b1 - b0, 2), "receipt": {"complete": r.complete, "records_tombstoned": r.records_tombstoned,
                                                    "batches": r.batches, "max_batch_ms": r.max_batch_ms,
                                                    "revisions_touched": r.revisions_touched},
        "commit_latency_A_before": _stats([c1 - c0 for c0, c1, _ in pre]),
        "commit_latency_B_during": _stats([c1 - c0 for c0, c1, _ in during]),
        "commit_latency_A_after": _stats([c1 - c0 for c0, c1, _ in post]),
        "commits_ok": ok_commits, "commit_errors": errors, "live_committer_nodes": live_oth,
        "verify": report.result, "verify_s": round(verify_s, 1),
        "history": {"head_seq": head_seq, "revisions": len(chain), "contiguous": contiguous,
                    "single_parent": single_parent},
    }
    with capsys.disabled():
        print("\nSC003-COMMITTER " + json.dumps(m, sort_keys=True), flush=True)
    if OUT:
        with open(OUT, "a") as fh:
            fh.write(json.dumps(m, sort_keys=True) + "\n")
    assert report.result == "equal", report.differences[:5]
    assert r.complete and r.records_tombstoned == nodes * PER_NODE
    assert live_oth == ok_commits, "a committed node is missing"
    assert contiguous and single_parent, m["history"]
    assert not errors, errors
    # SC-003 (Enterprise target): under 60 s and no commit blocked 1 s or more
    assert b1 - b0 < 60
    assert m["commit_latency_B_during"].get("max_ms", 0) < 1000
