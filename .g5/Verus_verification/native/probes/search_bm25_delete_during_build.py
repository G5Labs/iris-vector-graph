#!/usr/bin/env python3
"""BM25 Delete during a rebuild is lost (review round 2 domains R2-1; search model witness for the lost delete).

L1 (ADR-0007; spec 044 FR-018/FR-019; search.bm25.write_lock): writes to one index are serialised; a document the
caller deleted from the index is not returned by a later search. As built, Delete tests the index's N marker before
taking the lock (BM25Index.cls:498) and Build sets N only after its scan (:160), so a Delete that arrives while a
rebuild is scanning answers "not in the index" and the rebuild then publishes the document.

Two connections. A rebuilds index IX over NODES nodes; while it runs, B removes the probe documents from the graph
(the caller's upkeep: delete the node, then bm25_delete) one at a time, recording bm25_delete's answer. After both
finish, every deleted document is searched by its unique term. Expected: none is returned. INCONCLUSIVE when no
delete landed inside the rebuild's window.
"""
import threading
import time

from search_common import connect, engine, ensure_schema, reset, say

G = "g5probe_bm25_del"
IX = "g5pbm25del"
NODES = 4000
TARGETS = 40


def main() -> int:
    conn_a, native = connect()
    conn_b, _nb = connect()
    eng_a, eng_b = engine(conn_a), engine(conn_b)
    data = {"schema": ensure_schema(eng_a)}
    reset(eng_a, native)
    try:
        eng_a.bm25_drop(IX)
    except Exception:
        pass
    eng_a.bulk_create_nodes(
        [{"id": f"g5p:del:{i}", "labels": ["Doc"], "properties": {"name": f"common gamma{i % 30} uniq{i}"}}
         for i in range(NODES)], graph=G)
    eng_a.bm25_build(IX, ["name"], graph=G)
    window, deletes = {}, []
    stop = threading.Event()

    def builder():
        window["start"] = time.monotonic()
        try:
            window["result"] = str(eng_a.bm25_build(IX, ["name"], graph=G))
        except Exception as e:  # noqa: BLE001
            window["error"] = repr(e)
        window["end"] = time.monotonic()
        stop.set()

    def deleter():
        time.sleep(0.05)
        for k in range(TARGETS):
            if stop.is_set():
                break
            doc = f"g5p:del:{k}"
            t0 = time.monotonic()
            try:
                eng_b.delete_node(doc, graph=G)
            except Exception as e:  # noqa: BLE001
                deletes.append({"doc": doc, "node_delete_error": repr(e)})
                continue
            try:
                ok = eng_b.bm25_delete(IX, doc)
            except Exception as e:  # noqa: BLE001
                ok = repr(e)
            deletes.append({"doc": doc, "t": t0, "bm25_delete": ok})
            time.sleep(0.01)

    tb, td = threading.Thread(target=builder), threading.Thread(target=deleter)
    tb.start(); td.start(); tb.join(); td.join()
    inside = [d for d in deletes if "t" in d and window.get("start", 0) <= d["t"] <= window.get("end", 0)]
    resurrected = []
    for d in deletes:
        k = d["doc"].split(":")[-1]
        hits = eng_a.bm25_search(IX, f"uniq{k}", k=5)
        ids = [h[0] if isinstance(h, (list, tuple)) else (h.get("id") if isinstance(h, dict) else h) for h in (hits or [])]
        if d["doc"] in ids:
            resurrected.append({"doc": d["doc"], "bm25_delete": d.get("bm25_delete")})
    data.update({"window_s": round(window.get("end", 0) - window.get("start", 0), 3), "build": window.get("result") or window.get("error"),
                 "deletes": len(deletes), "inside_window": len(inside),
                 "false_answers_inside": sum(1 for d in inside if d.get("bm25_delete") is False),
                 "resurrected": resurrected})
    if not inside:
        return say("search_bm25_delete_during_build", "INCONCLUSIVE", f"no delete landed inside the {data['window_s']} s rebuild", data) and 0
    if resurrected:
        return say("search_bm25_delete_during_build", "OBSERVED_DEFECT",
                   f"{len(resurrected)} of {len(deletes)} deleted documents are still returned after the rebuild "
                   f"({data['false_answers_inside']} deletes inside the {data['window_s']} s window answered False)", data) and 0
    return say("search_bm25_delete_during_build", "OBSERVED_AS_EXPECTED",
               f"{len(inside)} deletes landed inside the rebuild and none of the {len(deletes)} documents is returned", data) and 0


if __name__ == "__main__":
    raise SystemExit(main())
