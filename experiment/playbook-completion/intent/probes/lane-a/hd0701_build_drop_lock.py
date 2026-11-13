"""HD-0701 probe: do BM25 Build and Drop respect the index write lock, and is Build all-or-nothing?

Contract cited (pin 3eaa79cf):
- docs/adr/0007-bm25-df-and-doc-record-schema-2.md:5 (bb98725f, 2026-10-08): schema 2 "does every write under an
  index-level lock in a transaction".
- specs/044-bm25-index/spec.md:165,167 FR-019 / FR-021: Insert and Delete take the index-level write lock and run in a
  transaction ("two writers never interleave"); FR-016/FR-018: df, N, totalLen consistent "at every committed point".
Deterministic interleaving (two IRIS processes, no timing race): process A takes the index write lock
^BM25Idx(name,"lock") exactly as Insert's critical section holds it; process B then calls the pin's public engine
methods on the same index.
- Control: B's bm25_insert must wait for the lock and fail after the index's lock_timeout (2 s here).
- Reading "every write is locked" (ADR-0007 literal, the working answer): B's bm25_build and bm25_drop also wait/fail.
- Reading "only incremental writers are locked" (FR-019/FR-021 literal, as-built per source): Build and Drop complete at
  once while another writer holds the lock.
- Early stop: an engine bm25_build whose property list holds only a blank name (accepted by BM25BuildInput) is an
  all-or-nothing violation if it removes the previous complete index and leaves none.
Verdict: fail if Build or Drop proceed under a held writer lock, or the early-stopped Build leaves no index.
Data: graph `ia-0701`, ids `ia0701:*`, index `ia0701`.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

G = "ia-0701"
IDX = "ia0701"
TEXT = {"ia0701:n1": "alpha bravo", "ia0701:n2": "bravo charlie", "ia0701:n3": "charlie delta",
        "ia0701:n4": "delta echo"}


def timed(label, fn, guard_s=20.0):
    """Run fn in a thread; report outcome and elapsed. A blocked call is reported after guard_s."""
    box = {}

    def run():
        t0 = time.monotonic()
        try:
            box["result"] = fn()
        except Exception as e:  # noqa: BLE001
            box["error"] = str(e)[:300]
        box["elapsed"] = round(time.monotonic() - t0, 3)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(guard_s)
    box["blocked_past_guard"] = th.is_alive()
    C.obs(step=label, **box)
    return box, th


def main() -> int:
    a = C.conn()
    b = C.conn()
    eb = C.engine(b)
    failures = []
    held = False
    try:
        C.obs(step="processes", a_pid=a.pid, b_pid=b.pid)
        for nid, text in TEXT.items():
            eb.create_node(nid, labels=["IA0701"], properties={"name": text}, graph=G)
        C.obs(step="baseline_build", result=eb.bm25_build(IDX, ["name"], graph=G))
        b.o.set(2, "^BM25Idx", IDX, "cfg", "lock_timeout")

        a.o.lock("", 5, "^BM25Idx", IDX, "lock")
        held = True
        C.obs(step="A_holds_writer_lock")

        ins, _ = timed("B_insert_while_locked", lambda: eb.bm25_insert(IDX, "ia0701:n5", "foxtrot"))
        if "error" not in ins:
            failures.append("control failed: Insert did not wait for the held lock")
        bld, th_b = timed("B_build_while_locked", lambda: eb.bm25_build(IDX, ["name"], graph=G))
        if th_b.is_alive():
            a.o.unlock("", "^BM25Idx", IDX, "lock")
            held = False
            th_b.join(30)
        C.obs(step="info_after_build", info=eb.bm25_info(IDX))
        if "result" in bld and bld["elapsed"] < 1.0:
            failures.append("Build completed while another writer held the index lock")
        if held:
            b.o.set(2, "^BM25Idx", IDX, "cfg", "lock_timeout")
            drp, th_d = timed("B_drop_while_locked", lambda: eb.bm25_drop(IDX))
            if th_d.is_alive():
                a.o.unlock("", "^BM25Idx", IDX, "lock")
                held = False
                th_d.join(30)
            C.obs(step="info_after_drop", info=eb.bm25_info(IDX),
                  global_defined=b.o.isDefined("^BM25Idx", IDX))
            if "error" not in drp and drp["elapsed"] < 1.0:
                failures.append("Drop completed while another writer held the index lock")
        if held:
            a.o.unlock("", "^BM25Idx", IDX, "lock")
            held = False
            C.obs(step="A_released_writer_lock")

        # Early-stopped Build: a blank property name passes BM25BuildInput; Build kills first, then returns.
        C.obs(step="rebuild", result=eb.bm25_build(IDX, ["name"], graph=G), info=eb.bm25_info(IDX))
        try:
            r = eb.bm25_build(IDX, [" "], graph=G)
            C.obs(step="blank_prop_build", accepted=True, result=r)
        except Exception as e:  # noqa: BLE001
            C.obs(step="blank_prop_build", accepted=False, error=str(e)[:300])
        info = eb.bm25_info(IDX)
        C.obs(step="info_after_blank_build", info=info, global_defined=b.o.isDefined("^BM25Idx", IDX),
              search=eb.bm25_search(IDX, "bravo", k=5))
        if "N" not in info:
            failures.append("a Build that indexed nothing removed the previous complete index and left none")
    finally:
        if held:
            a.o.unlock("", "^BM25Idx", IDX, "lock")
        try:
            eb.bm25_drop(IDX)
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=str(ex)[:200])
        eb.erase_graph(G)
        C.obs(step="cleanup", index_defined=b.o.isDefined("^BM25Idx", IDX),
              graph_rows_left=b.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", G))
        a.close()
        b.close()
    if failures:
        C.verdict("fail", "; ".join(failures))
    else:
        C.verdict("pass", "Build and Drop wait for the index write lock and a stopped Build keeps the old index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
