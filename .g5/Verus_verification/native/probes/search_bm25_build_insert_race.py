#!/usr/bin/env python3
"""O1 / F2 — BM25 Build takes no lock: Inserts that commit while it runs.

Model: search.rs witness_build_insert_breaks_n and witness_build_insert_double_df (W-O1a/b); the
repair theorem theorem_locked_build_preserves. L1 (spec 044 FR-016, FR-018, FR-019; ADR-0007 "does
every write under an index-level lock in a transaction"): at every committed point df(t) equals the
number of tf(t,*) postings, the token record of d is its postings' terms, N = |len|, totalLen = sum
len, vocab_size = |df|.

Two connections (two IRIS processes). Connection A runs bm25_build over a graph of NODES nodes; while
it runs, connection B inserts documents into the same index name: half of them ids Build will also
scan (W-O1b), half ids it will not (W-O1a). After both finish (no Build in flight) the stored index
is read back and the L1 counters are recomputed by brute force from tf and len. Expected: no
violation. The race is timing-dependent: if no Insert committed inside Build's window the probe is
INCONCLUSIVE.
"""
import threading
import time

from search_common import bm25_state, bm25_violations, connect, engine, ensure_schema, reset, say

G = "g5probe_bm25_race"
IX = "g5pbm25race"
NODES = 3000


def main() -> int:
    conn_a, native = connect()
    conn_b, _native_b = connect()
    eng_a = engine(conn_a)
    eng_b = engine(conn_b)
    data = {"schema": ensure_schema(eng_a)}
    reset(eng_a, native)
    try:
        eng_a.bm25_drop(IX)
    except Exception:
        pass
    eng_a.bulk_create_nodes(
        [{"id": f"g5p:race:{i}", "labels": ["Doc"], "properties": {"name": f"common alpha{i % 50} beta{i % 7}"}}
         for i in range(NODES)], graph=G)
    # an index must exist (schema 2) so that a pre-Kill Insert is a normal write
    eng_a.bm25_build(IX, ["name"], graph=G)

    window = {}
    inserts = []
    errors = []
    stop = threading.Event()

    def builder():
        window["start"] = time.monotonic()
        try:
            window["result"] = eng_a.bm25_build(IX, ["name"], graph=G)
        except Exception as e:  # recorded, not swallowed silently
            window["error"] = repr(e)
        window["end"] = time.monotonic()
        stop.set()

    def inserter():
        k = 0
        while not stop.is_set() and k < 400:
            doc = f"g5p:race:{k}" if k % 2 == 0 else f"g5p:extra:{k}"
            t0 = time.monotonic()
            try:
                ok = eng_b.bm25_insert(IX, doc, f"common zeta extra{k}")
                inserts.append({"doc": doc, "t0": t0, "t1": time.monotonic(), "ok": ok})
            except Exception as e:
                errors.append({"doc": doc, "t0": t0, "t1": time.monotonic(), "error": repr(e)[:300]})
            k += 1

    tb = threading.Thread(target=builder)
    ti = threading.Thread(target=inserter)
    tb.start()
    time.sleep(0.05)
    ti.start()
    tb.join()
    ti.join()

    inside = [i for i in inserts if window.get("start", 0) < i["t0"] and i["t1"] < window.get("end", 0)]
    st = bm25_state(native, IX)
    viol = bm25_violations(st)
    data.update({
        "build_window_s": (window.get("end", 0) - window.get("start", 0)),
        "build_result": window.get("result"), "build_error": window.get("error"),
        "inserts": len(inserts), "inserts_inside_build": len(inside),
        "insert_errors": errors[:20], "cfg": {k: str(v) for k, v in st["cfg"].items()},
        "len_nodes": len(st["len"]), "df_nodes": len(st["df"]), "violations": viol[:50],
        "violation_count": len(viol),
    })
    eng_a.bm25_drop(IX)
    reset(eng_a, native)

    if viol:
        say("search_bm25_build_insert_race", "OBSERVED_DEFECT",
            f"{len(viol)} L1 violation(s) with no Build in flight, e.g. {viol[:3]}; "
            f"{len(inside)} Insert(s) committed inside Build's {data['build_window_s']:.2f}s window", data)
    elif not inside:
        say("search_bm25_build_insert_race", "INCONCLUSIVE",
            f"no Insert committed inside Build's window ({len(inserts)} inserts, {len(errors)} errors)", data)
    else:
        say("search_bm25_build_insert_race", "OBSERVED_AS_EXPECTED",
            f"{len(inside)} Insert(s) committed during Build and the stored counters are consistent", data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
