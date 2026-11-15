#!/usr/bin/env python3
"""F-0701 live: a BM25 Insert from a second IRIS process while a Build of the same index runs (AUDITB, lane B).

    bash experiment/playbook-completion/tools/locks.sh iris \
        python experiment/playbook-completion/live/breadth-b/07_race.py [n_nodes]

Process A builds index b07r over n nodes of graph b07g5 (Graph.KG.BM25Index.Build: Kill, then per-document writes, then
the header; no lock, no transaction). Process B inserts one extra document (Insert: write lock + transaction) part way
through. Process C polls Info. Afterwards the index is checked against its own records: TXT-I2 says that after each
committed write the document count and total length match the stored documents. The journal (independent oracle)
shows each process's writes and transactions. Scratch: graph b07g5, index b07r; removed at the end.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import capture, gget, gsubs, session, write_log, J, DB, NAMESPACE  # noqa: E402
from iris_conn import Conn  # noqa: E402

G5, NAME = "b07g5", "b07r"


def state(c):
    n = gget(c, NAME, "cfg", "N", root="BM25Idx")
    tl = gget(c, NAME, "cfg", "totalLen", root="BM25Idx")
    docs = gsubs(c, "BM25Idx", NAME, "doc")
    lens = [int(gget(c, NAME, "len", d, root="BM25Idx") or 0) for d in gsubs(c, "BM25Idx", NAME, "len")]
    return {"N": n, "totalLen": tl, "schema": gget(c, NAME, "cfg", "schema", root="BM25Idx"),
            "graph": gget(c, NAME, "cfg", "graph", root="BM25Idx"), "doc_records": len(docs), "sum_len": sum(lens),
            "extra_doc_present": "b07_extra" in docs}


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    with session("07-f0701-race") as s:
        s.eng.bm25_drop(NAME)
        s.eng.erase_graph(G5)
        t0 = time.time()
        s.eng.bulk_create_nodes([{"id": f"b07_r{i:05d}", "labels": ["B07R"],
                                  "properties": {"name": f"alpha{i % 97} beta{i % 13} gamma word{i}"}}
                                 for i in range(n)], disable_indexes=False, graph=G5)
        seed_s = time.time() - t0
        # calibrate: one Build alone
        t0 = time.time()
        s.eng.bm25_build(NAME, ["name"], graph=G5)
        build_s = time.time() - t0
        calib = state(s.c)
        cB, cC = s.conn2(), s.conn2()
        engB = s.engine_on(cB, embedding_dimension=4)
        res = {"insert": None, "insert_error": None, "polls": []}
        stop = threading.Event()

        def inserter():
            time.sleep(build_s * 0.4)
            try:
                res["insert"] = engB.bm25_insert(NAME, "b07_extra", "extraordinary unique words")
                res["insert_at"] = time.time()
            except Exception as e:
                res["insert_error"] = f"{type(e).__name__}: {e}"

        def poller():
            while not stop.is_set():
                try:
                    info = json.loads(str(cC.call("Graph.KG.BM25Index", "Info", NAME)))
                except Exception as e:
                    info = {"error": str(e)}
                res["polls"].append([round(time.time(), 3), info.get("N"), info.get("schema")])
                time.sleep(0.05)

        m = J.mark()
        tb = threading.Thread(target=inserter)
        tp = threading.Thread(target=poller)
        tp.start()
        tb.start()
        t_build0 = time.time()
        build_res = s.eng.bm25_build(NAME, ["name"], graph=G5)
        t_build1 = time.time()
        tb.join(timeout=120)
        stop.set()
        tp.join(timeout=30)
        recs = J.records_since(m, dbs={DB})
        pids = {s.c.pid: "A-build", cB.pid: "B-insert"}
        recs = [r for r in recs if r["p"] in pids]
        txns = J.transactions(recs)
        by_proc = {}
        for u in txns:
            k = pids[u["pid"]]
            d = by_proc.setdefault(k, {"txn": 0, "auto": 0, "records": 0})
            d[u["kind"]] += 1
            d["records"] += len(u["records"])
        final = state(s.c)
        hits = s.eng.bm25_search(NAME, "extraordinary", k=3)
        polls = res["polls"]
        seen = sorted({(p[1], p[2]) for p in polls}, key=lambda x: str(x))
        insert_during = res.get("insert_at") and t_build0 < res["insert_at"] < t_build1
        i2_ok = final["N"] == final["doc_records"] and final["totalLen"] == final["sum_len"]
        out = {"n_nodes": n, "seed_seconds": round(seed_s, 2), "calibration_build_seconds": round(build_s, 2),
               "calibration_state": calib, "race_build_result": build_res,
               "race_build_seconds": round(t_build1 - t_build0, 2), "insert_result": res["insert"],
               "insert_error": res["insert_error"], "insert_landed_during_build": bool(insert_during),
               "final_state": final, "search_extraordinary": hits, "TXT-I2_holds": i2_ok,
               "reader_views_N_schema": seen[:30], "n_polls": len(polls),
               "journal_by_process": by_proc,
               "verdict": ("defect-reproduced" if (insert_during and not i2_ok) else
                           "holds" if (insert_during and i2_ok) else "inconclusive"),
               "contract": "TXT-I2 (counts match stored documents after each committed write), TXT-I5 / TXT-B1.11 (no two writers at once), ADR-0007"}
        s.eng.bm25_drop(NAME)
        s.eng.erase_graph(G5)
        print(write_log(s, out))
        print(json.dumps({k: out[k] for k in ("verdict", "insert_landed_during_build", "final_state", "TXT-I2_holds", "race_build_seconds", "journal_by_process")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
