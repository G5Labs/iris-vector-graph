#!/usr/bin/env python3
"""Candidate F-C0702: a BM25 Insert/Delete that fails inside a caller's open transaction rolls the caller's work back.

    python experiment/playbook-completion/live/breadth-b/07_nested_rollback.py

BM25Index.Insert (iris_src/src/Graph/KG/BM25Index.cls:457-490) and Delete (:502-511) run `TStart` and, on any error
inside their Try, `If $TLevel > 0 TRollback` -- a TROLLBACK with no argument, which ends every transaction level, the
caller's included. The product's own transaction design (iris_vector_graph/_write_txn.py:1-30) nests IVG writes in a
caller's transaction and undoes only its own level (TROLLBACK 1). Here, on one IRIS process (one Conn: SQL and Native
API share it): SQL START TRANSACTION, a caller row in Graph_KG.docs (scratch graph b07g6), then
(a) control: a valid bm25_insert -> $TLEVEL back to the caller's level, the caller row still there;
(b) a bm25_insert whose document id is longer than a global subscript may be -> it raises; then $TLEVEL and the caller
    row are read. The caller then ROLLBACKs (or finds nothing to roll back). Scratch removed at the end.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import capture, session, write_log, J  # noqa: E402

G6, NAME = "b07g6", "b07t"


def tlevel(c):
    return c.sql("SELECT $TLEVEL")[0][0]


def caller_rows(c):
    return c.sql("SELECT COUNT(*) FROM Graph_KG.docs WHERE graph_id = ?", G6)[0][0]


def main():
    with session("07-fc0702-nested-rollback") as s:
        s.eng.bm25_drop(NAME)
        s.c.sql("DELETE FROM Graph_KG.docs WHERE graph_id = ?", G6)
        s.eng.bm25_insert(NAME, "b07_seed", "seed words")  # the index exists, schema 2
        out = {}
        for case, doc_id in (("control-valid-insert", "b07_ok"), ("failing-insert", "b07_" + "x" * 600)):
            cur = s.c.conn.cursor()
            cur.execute("START TRANSACTION")
            cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", [G6, "b07_tx_" + case[:7], "caller row"])
            before = {"tlevel": tlevel(s.c), "caller_rows": caller_rows(s.c)}
            cap = capture(s, lambda: s.eng.bm25_insert(NAME, doc_id, "alpha beta"))
            after = {"tlevel": tlevel(s.c), "caller_rows": caller_rows(s.c)}
            cur.execute("ROLLBACK")
            final = {"tlevel": tlevel(s.c), "caller_rows": caller_rows(s.c)}
            cur.close()
            out[case] = {"before_call": before, "call_result": cap.result, "call_error": (cap.error or "")[:300],
                         "after_call": after, "after_caller_rollback": final,
                         "journal_transactions": cap.txn_summary(s.smap)}
        f = out["failing-insert"]
        ctl = out["control-valid-insert"]
        out["verdict"] = ("defect-reproduced" if (f["call_error"] and f["before_call"]["tlevel"] >= 1 and f["after_call"]["tlevel"] == 0
                                                 and f["after_call"]["caller_rows"] == 0 and ctl["after_call"]["tlevel"] == ctl["before_call"]["tlevel"]
                                                 and ctl["after_call"]["caller_rows"] == 1) else "holds-or-inconclusive")
        out["contract"] = ("iris_vector_graph/_write_txn.py:1-30 (an IVG write nested in a caller's transaction undoes only its own "
                           "level); spec 044 FR-019 (a failure leaves the index as it was); SYS-I3 (a refused command leaves every store as it was)")
        s.eng.bm25_drop(NAME)
        s.c.sql("DELETE FROM Graph_KG.docs WHERE graph_id = ?", G6)
        print(write_log(s, out))
        print(out["verdict"], {k: (v["before_call"], v["after_call"], v["call_error"][:80]) for k, v in out.items() if isinstance(v, dict) and "before_call" in v})


if __name__ == "__main__":
    main()
