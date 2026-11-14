#!/usr/bin/env python3
"""O2 / F4 — two bm25_upgrade calls on one schema-1 index, with Searches running.

Model: search.rs witness_concurrent_upgrades (W-O2a); as-built theorem theorem_upgrade_step_preserves
holds only under the premise that Upgrades are serial; repair theorem theorem_repaired_upgrade_preserves.
L1 (spec 044 FR-023): a Search running during Upgrade never observes schema 2 before the conversion is
complete; writers are refused while Upgrade runs; the end state equals a fresh conversion.

Fixture: a schema-1 index is written as 3.x wrote it (tf, len, stored idf, N, avgdl, k1, b,
vocab_size; no df, doc, totalLen or schema), the same way tests/integration/test_044_bm25_incremental.py
write_schema1 does — there is no public entry point that creates a schema-1 index. Then only public
entry points run: bm25_upgrade on two connections at once, bm25_search on a third. (The model's other
half of W-O2a — a writer admitted between the first call's unlock and the second call's lock — is a
microsecond window and is not attempted here.) (for a term every
document holds, so an empty answer means the Search read schema 2 with that term's df missing).
Timing-dependent: if the second call answers "already" the race did not happen (INCONCLUSIVE).
"""
import math
import threading
import time

from search_common import bm25_state, bm25_violations, connect, engine, ensure_schema, reset, say

IX = "g5pbm25upg"
DOCS = 6000


def write_schema1(native, name, n):
    total = 0
    for i in range(n):
        toks = ["qeverywhere", f"qbucket{i % 97}", f"qid{i}"]
        total += len(toks)
        native.set(len(toks), "BM25Idx", name, "len", f"u:{i}")
        for t in toks:
            native.set(1, "BM25Idx", name, "tf", t, f"u:{i}")
    df = {"qeverywhere": n}
    for i in range(n):
        df[f"qbucket{i % 97}"] = df.get(f"qbucket{i % 97}", 0) + 1
        df[f"qid{i}"] = 1
    for t, c in df.items():
        native.set(math.log((n - c + 0.5) / (c + 0.5) + 1), "BM25Idx", name, "idf", t)
    native.set(n, "BM25Idx", name, "cfg", "N")
    native.set(total / n, "BM25Idx", name, "cfg", "avgdl")
    native.set(1.5, "BM25Idx", name, "cfg", "k1")
    native.set(0.75, "BM25Idx", name, "cfg", "b")
    native.set(len(df), "BM25Idx", name, "cfg", "vocab_size")


def main() -> int:
    conn0, native = connect()
    conn1, _n1 = connect()
    conn2, _n2 = connect()
    eng0, eng1, eng2 = engine(conn0), engine(conn1), engine(conn2)
    ensure_schema(eng0)
    reset(eng0, native)
    try:
        eng0.bm25_drop(IX)
    except Exception:
        pass
    write_schema1(native, IX, DOCS)
    data = {"info_before": eng0.bm25_info(IX)}
    if data["info_before"].get("schema") != 1:
        say("search_bm25_upgrade_concurrent", "INCONCLUSIVE", f"fixture is not schema 1: {data['info_before']}", data)
        return 0

    results = {}
    empties = []
    searches = [0]
    done = threading.Event()

    def upgrade(tag, eng):
        t0 = time.monotonic()
        try:
            results[tag] = eng.bm25_upgrade(IX)
        except Exception as e:
            results[tag] = {"error": repr(e)[:300]}
        results[tag + "_t"] = (t0, time.monotonic())

    def searcher():
        while not done.is_set():
            hits = eng0.bm25_search(IX, "qeverywhere", 3)
            searches[0] += 1
            if not hits:
                empties.append(time.monotonic())

    s = threading.Thread(target=searcher)
    s.start()
    u1 = threading.Thread(target=upgrade, args=("first", eng1))
    u2 = threading.Thread(target=upgrade, args=("second", eng2))
    u1.start()
    time.sleep(0.02)
    u2.start()
    u1.join()
    u2.join()
    done.set()
    s.join()
    st = bm25_state(native, IX)
    viol = bm25_violations(st)
    data.update({"upgrade": results, "searches": searches[0], "empty_answers": len(empties),
                 "violations_after": viol[:20], "info_after": eng0.bm25_info(IX)})
    eng0.bm25_drop(IX)

    both_ran = all(isinstance(results.get(t), dict) and results[t].get("upgraded") == 1 for t in ("first", "second"))
    if empties or viol:
        say("search_bm25_upgrade_concurrent", "OBSERVED_DEFECT",
            f"two Upgrades ({results.get('first')}, {results.get('second')}); {len(empties)} of {searches[0]} Searches for a "
            f"term in every document answered nothing; violations after: {viol[:3]}", data)
    elif not both_ran:
        say("search_bm25_upgrade_concurrent", "INCONCLUSIVE",
            f"the second call did not run a conversion ({results.get('second')}); the race window was missed", data)
    else:
        say("search_bm25_upgrade_concurrent", "OBSERVED_AS_EXPECTED",
            f"both calls converted, {searches[0]} Searches all answered, end state consistent", data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
