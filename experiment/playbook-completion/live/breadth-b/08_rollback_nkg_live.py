#!/usr/bin/env python3
"""A rolled-back Cypher write and the interned snapshot ^NKG (candidate new finding; CYP-I6.4 rollback + SYS-I8).

    python experiment/playbook-completion/live/breadth-b/08_rollback_nkg_live.py

Graph.KG.Adjacency.Put (reached from the rdf_edges functional index inside the row's transaction) interns a new edge
into ^NKG when ^NKG is built: it SETs ^NKG(-1,..)/(-2,..) (transactional) and $Increments ^NKG(-3, src) (out-degree),
^NKG("$meta","edgeCount") and ("version") (iris_src/src/Graph/KG/Adjacency.cls:95-107). $Increment is not undone by
TROLLBACK. A Cypher write query whose later statement fails rolls back (query.py:1946-1966): the edge row and the ^NKG
edge entries go, the counters stay. This script measures that on scratch nodes, journal-backed.
"""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c08", HERE / "08_common.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def nkg_state(s, src, dst):
    o = s.c.o
    si = o.get("NKG", "$NI", src) if o.isDefined("NKG", "$NI", src) else None
    di = o.get("NKG", "$NI", dst) if o.isDefined("NKG", "$NI", dst) else None
    deg = o.get("NKG", -3, si) if si is not None and o.isDefined("NKG", -3, si) % 10 == 1 else None
    # count actual -1 entries under src
    n_out = 0
    if si is not None:
        for _ in o.iterator("NKG", -1, si).subscripts():
            n_out += 1
    return {"src_idx": si, "dst_idx": di, "deg(-3,src)": deg, "out_pred_groups(-1,src)": n_out,
            "edgeCount": o.get("NKG", "$meta", "edgeCount") if o.isDefined("NKG", "$meta", "edgeCount") else None,
            "stale": o.get("NKG", "$meta", "stale") if o.isDefined("NKG", "$meta", "stale") else None,
            "rows_out_of_src": s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ?", src)[0][0]}


def main():
    R = {}
    with C.session08("08-rollback-nkg", native_cypher=False) as s:
        R["ledger_meta"] = C.ledger_meta(s)
        C.cleanup(s)
        C.run(s, "CREATE (:B08RN {id:'b08_r1'}), (:B08RN {id:'b08_r2'}), (:B08RN {id:'b08_r3'})")
        C.run(s, "MATCH (a:B08RN {id:'b08_r1'}), (b:B08RN {id:'b08_r3'}) CREATE (a)-[:B08OLD]->(b)")
        C.run(s, "CREATE (a:B08J {id:'b08_j5'})-[:B08T]->(b:B08J {id:'b08_j6'})")
        R["sync"] = str(s.eng.sync())[:200]
        R["before"] = nkg_state(s, "b08_r1", "b08_r2")
        q = ("MATCH (a:B08RN {id:'b08_r1'}), (b:B08RN {id:'b08_r2'}) CREATE (a)-[:B08NEW]->(b) "
             "CREATE (c:B08J {id:'b08_j5'})-[:B08T]->(d:B08J {id:'b08_j6'})")
        cap = C.capture(s, lambda: s.eng.execute_cypher(q), pids={s.c.pid})
        R["query"] = q
        R["error"] = cap.error
        R["after"] = nkg_state(s, "b08_r1", "b08_r2")
        R["journal_nkg"] = [{"t": r["t"], "in_txn": r["x"], "g": r["g"],
                             "new": None if r["n"] is None else base64.b64decode(r["n"])[:20].decode("latin1")}
                            for r in cap.records if r["g"].startswith(("^NKG", '^KG("gen"', '^KG("__version"'))]
        rb, af = R["before"], R["after"]
        R["drift"] = {"deg_before": rb["deg(-3,src)"], "deg_after": af["deg(-3,src)"],
                      "edgeCount_before": rb["edgeCount"], "edgeCount_after": af["edgeCount"],
                      "rows_before": rb["rows_out_of_src"], "rows_after": af["rows_out_of_src"],
                      "stale_after": af["stale"]}
        repro = (cap.error is not None and rb["rows_out_of_src"] == af["rows_out_of_src"]
                 and str(rb["deg(-3,src)"]) != str(af["deg(-3,src)"]) and not af["stale"])
        R["oracle"] = ("SYS-I8 (CONTEXT.md:109-120): a derived store matches its sources or says it is out of date; "
                       "CYP-I6.4: a failed write query takes back all of its steps")
        R["verdict"] = "reproduced" if repro else "not-reproduced"
        R["cleanup"] = C.cleanup(s)
        try:
            R["resync"] = str(s.eng.sync())[:200]  # rebuild ^NKG from the rows: leaves no drift behind
            R["after_resync_edgeCount"] = s.c.o.get("NKG", "$meta", "edgeCount") if s.c.o.isDefined("NKG", "$meta", "edgeCount") else None
        except Exception as e:  # noqa: BLE001
            R["resync"] = f"{type(e).__name__}: {e}"
        p = C.write_log(s, R, name="08-rollback-nkg")
    print(p)
    print(json.dumps({k: R[k] for k in ("error", "before", "after", "drift", "verdict")}, default=str, indent=1))


if __name__ == "__main__":
    main()
