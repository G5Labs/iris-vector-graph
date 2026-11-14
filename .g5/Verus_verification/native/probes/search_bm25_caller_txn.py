#!/usr/bin/env python3
"""O1 / F3 — BM25 Insert inside a caller's transaction.

The engine here is built on a plain DB-API connection, so its native calls run in the caller's own IRIS
process (engine._iris_obj falls back to createIRIS(conn); see erasure_caller_transaction.py Part A):
BM25Index.Insert's TStart nests in the caller's transaction.

Part A — the Catch's `If $TLevel > 0 TRollback` (BM25Index.cls:487) rolls back every level. Trigger: a
document id too long to be a global subscript (<SUBSCRIPT> inside the Try, at RemoveDoc's $Data).
Expected (IVG policy, _write_txn.py 4.6.4 "takes back IVG's level alone, so a failed write leaves the
caller's earlier work"; Eraser's `While $TLevel > tTxnLevel { TROLLBACK 1 }`): bm25_insert raises,
the caller is still in its transaction, and the node it created earlier in that transaction is there
after the caller commits.

Part B — model witness_caller_txn_rollback (W-O1d) assumes the inner `Lock -` releases the index lock
before the caller's transaction ends (premise P_unlock_in_txn). Observation: a second process's Insert
is timed while the first process's transaction is open; then the caller rolls back and the stored
counters are checked against L1 (spec 044 FR-016/FR-018). If the second Insert waited for the
rollback, IRIS kept the lock to the end of the transaction and the lost-update branch of F3 is not
reachable.
"""
import threading
import time

from search_common import bm25_state, bm25_violations, connect, engine, ensure_schema, reset, say, tlevel

G = "g5probe_bm25_txn"
IX = "g5pbm25txn"
KEEP = "g5p:txn:keep"


def node_count(conn, node_id: str) -> int:
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ? AND graph_id = ?", [node_id, G])
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def part_a(conn0, eng0, native) -> None:
    reset(eng0, native)
    try:
        eng0.bm25_drop(IX)
    except Exception:
        pass
    eng0.bm25_insert(IX, "seed", "lambda")  # an existing schema-2 index
    conn1, _n1 = connect()
    eng1 = engine(conn1)
    cur = conn1.cursor(); cur.execute("START TRANSACTION"); cur.close()
    created = eng1.create_node(KEEP, labels=["Doc"], properties={"name": "kept"}, graph=G)
    level_before = tlevel(conn1)
    raised = None
    try:
        eng1.bm25_insert(IX, "d" * 1200, "omega")
    except Exception as e:
        raised = repr(e)[:400]
    level_after = tlevel(conn1)
    visible_in_txn = node_count(conn1, KEEP)
    try:
        conn1.commit()
        commit_error = None
    except Exception as e:
        commit_error = repr(e)[:300]
    persisted = node_count(conn0, KEEP)
    data = {"created": created, "tlevel_before_insert": level_before, "insert_raised": raised,
            "tlevel_after_failed_insert": level_after, "node_visible_in_caller_txn": visible_in_txn,
            "commit_error": commit_error, "node_persisted_after_commit": persisted,
            "expected": {"insert_raises": True, "tlevel_after": level_before, "node_persisted_after_commit": 1}}
    try:
        conn1.close()
    except Exception:
        pass
    if raised is None:
        say("search_bm25_caller_txn_rollback", "INCONCLUSIVE", "the over-long document id did not make Insert fail", data)
    elif persisted == 1 and level_after == level_before:
        say("search_bm25_caller_txn_rollback", "OBSERVED_AS_EXPECTED",
            f"Insert failed ({raised[:80]}) and the caller's earlier node survived its commit", data)
    else:
        say("search_bm25_caller_txn_rollback", "OBSERVED_DEFECT",
            f"a failed bm25_insert inside the caller's transaction left $TLEVEL {level_before}->{level_after}; "
            f"the node the caller created earlier in it is {'gone' if persisted == 0 else 'present'} after the caller's commit", data)


def part_b(conn0, eng0, native) -> None:
    reset(eng0, native)
    try:
        eng0.bm25_drop(IX)
    except Exception:
        pass
    eng0.bm25_insert(IX, "seed", "lambda")
    conn1, _n1 = connect()
    eng1 = engine(conn1)
    cur = conn1.cursor(); cur.execute("START TRANSACTION"); cur.close()
    ok1 = eng1.bm25_insert(IX, "b1", "kappa")
    level_after_inner = tlevel(conn1)
    timing = {}

    def second():
        t0 = time.monotonic()
        try:
            timing["ok"] = eng0.bm25_insert(IX, "b2", "kappa")
        except Exception as e:
            timing["error"] = repr(e)[:300]
        timing["elapsed"] = time.monotonic() - t0

    th = threading.Thread(target=second)
    th.start()
    time.sleep(3.0)
    finished_before_rollback = not th.is_alive()
    conn1.rollback()
    th.join()
    st = bm25_state(native, IX)
    viol = bm25_violations(st)
    data = {"first_insert": ok1, "tlevel_after_inner_commit": level_after_inner, "second": timing,
            "second_finished_before_caller_rollback": finished_before_rollback,
            "violations_after_rollback": viol, "cfg": {k: str(v) for k, v in st["cfg"].items()},
            "postings": sorted(f"{t}/{d}" for (t, d) in st["tf"])}
    try:
        conn1.close()
    except Exception:
        pass
    eng0.bm25_drop(IX)
    if viol:
        say("search_bm25_caller_txn_lock", "OBSERVED_DEFECT",
            f"second Insert {'did not wait' if finished_before_rollback else 'waited'} for the caller; after the caller's rollback: {viol[:3]}", data)
    elif finished_before_rollback:
        say("search_bm25_caller_txn_lock", "INCONCLUSIVE",
            "the second Insert committed while the caller's transaction was open, yet the counters are consistent after the rollback", data)
    else:
        say("search_bm25_caller_txn_lock", "OBSERVED_AS_EXPECTED",
            f"the second Insert waited {timing.get('elapsed', 0):.1f}s for the caller's transaction (IRIS kept the lock), counters consistent", data)


def main() -> int:
    conn0, native = connect()
    eng0 = engine(conn0)
    ensure_schema(eng0)
    part_a(conn0, eng0, native)
    part_b(conn0, eng0, native)
    reset(eng0, native)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
