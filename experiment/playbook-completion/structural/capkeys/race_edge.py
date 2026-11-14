#!/usr/bin/env python3
"""Module 03: racing create_edge calls on one new edge (AUDITD, live).

    locks.sh iris python race_edge.py OUT.json

Found by keys.py (03-concurrent-create): four create_edge calls on one new triple whose target node did not exist
gave two errors (-121) and two False answers, and no edge row. Here, per trial (fresh namespace): four connections
released together call create_edge("rx:1", "R", "rx:2"). Variant A: only rx:1 exists (create_edge registers the
missing endpoint). Variant B: both endpoints exist. Oracle: WRT-B4.2/B4.9 (03-writes.md: an edge that exists makes
create_edge answer False; when two writers race to create one edge, one adds it and the other answers False): after
the race the edge exists exactly once, exactly one call answered True, and an answer False is given only when the
edge exists; an error is allowed only if the edge then exists or the caller is told nothing was written.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import concurrently, keys_check  # noqa: E402
from fk import fk_check  # noqa: E402


def trial(variant):
    c = lib.conn()
    try:
        lib.reset(c)
        e = lib.engine(c)
        e.create_node("rx:1")
        if variant == "B":
            e.create_node("rx:2")
        c.conn.commit()
        ans = concurrently(4, lambda i, cc, ee: ee.create_edge("rx:1", "R", "rx:2"))
        edges = c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = 'rx:1' AND o_id = 'rx:2'")[0][0]
        nodes = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'rx:2'")[0][0]
        def short(a):
            if a.get("ok"):
                return a.get("answer")
            m = re.search(r"SQLCODE -?(\d+)", a.get("error", ""))
            return "error SQLCODE -" + m.group(1) if m else "error " + a.get("error", "")[:60]
        answers = [short(a) for a in ans]
        trues = sum(1 for a in answers if a == "True")
        falses = sum(1 for a in answers if a == "False")
        false_without_edge = falses > 0 and edges == 0
        ok = edges == 1 and trues == 1
        kc, fc = keys_check(c)["violations"], fk_check(c)["violations"]
        return {"variant": variant, "answers": answers, "edge_rows": edges, "target_node_rows": nodes, "true": trues,
                "false": falses, "false_answered_but_no_edge": false_without_edge, "wrt_b4_9_holds": ok,
                "key_violations": kc, "fk_violations": fc}
    finally:
        lib.reset(c)
        c.close()


def main() -> int:
    outp = Path(sys.argv[1])
    res = []
    for variant in ("A", "B"):
        for t in range(8):
            r = trial(variant)
            r["trial"] = t
            res.append(r)
            print(json.dumps(r), flush=True)
            lib.dump(outp, res)
    summ = {}
    for v in ("A", "B"):
        rs = [r for r in res if r["variant"] == v]
        summ[v] = {"trials": len(rs), "holds": sum(r["wrt_b4_9_holds"] for r in rs),
                   "no_edge": sum(r["edge_rows"] == 0 for r in rs),
                   "false_but_no_edge": sum(r["false_answered_but_no_edge"] for r in rs)}
    lib.dump(outp, {"trials": res, "summary": summ})
    print(json.dumps(summ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
