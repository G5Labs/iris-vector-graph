#!/usr/bin/env python3
"""Module 10 lock plans, live on AUDITD (gate 3.5-lockplans).

    locks.sh iris python nkg_probes.py OUT_DIR [--only NAME ...]

Locks of module 10 (draft $RUN_DIR/lockplans/drafts/10.md section 1): ^IVG.NKGBuild exclusive, 900 s, taken by
TraversalBuild.BuildNKG (TraversalBuild.cls:293/303) and EnsureNKG (:410/:422, after an unlocked pre-check :403-409
and a re-check under the lock :415); the interning locks ^NKG("$NI", id) / ^NKG("$LI", label) (GraphIndex.cls:43-100:
lock-free fast path $Get, then Lock :0, then :5, re-check, allocate). Algorithm reads take no lock (ALG-P6).

  P1a (LP-10-3): an edge writer does not wait for ^IVG.NKGBuild (writers keep writing during a rebuild,
       CHANGELOG.md:2543-2555; TraversalBuild.cls:281-283).
  P1b (LP-10-2): after an erase marks ^NKG invalidated (Eraser.cls:1038-1053), two algorithm readers both wait for
       ^IVG.NKGBuild in EnsureNKG; after the release exactly one rewrites ^NKG, the other finds it rebuilt (:415).
  P2  (LP-10-6): interning under rollback. A writes an edge with a new label inside a caller transaction (it allocates
       ^NKG("$LI", label) = k under the lock, which a rollback undoes); B writes an edge with the same label, reads k
       on the lock-free fast path (GraphIndex.cls:82-83) and commits; A rolls back. Oracle ALG-B12.7 (a reader of the
       snapshot sees the same edges as the adjacency index, or learns that it is out of date; CONTEXT.md:109-114).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpcommon as L  # noqa: E402
import holdprobe as H  # noqa: E402

NKGB = ("^IVG.NKGBuild", ())


def setup_triangle(sd):
    for a, b in (("lp|1", "lp|2"), ("lp|2", "lp|3"), ("lp|3", "lp|1")):
        sd.e.create_edge(a, "R", b)
    sd.c.conn.commit()
    sync = str(sd.e.sync())[:300]
    sd.c.conn.commit()
    return {"sync": sync, "indexed": str(sd.o.classMethodValue("Graph.KG.Adjacency", "Indexed")),
            "ni_lp1": H.gget(sd, "^NKG", "$NI", "lp|1"), "nodeCount": H.gget(sd, "^NKG", "$meta", "nodeCount")}


def setup_invalidated(sd):
    s = setup_triangle(sd)
    s["erase_edges"] = str(sd.o.classMethodValue("Graph.KG.Eraser", "EraseEdges", "",
                                                  json.dumps([{"s": "lp|3", "p": "R", "o": "lp|1"}])))
    sd.c.conn.commit()
    s["invalidated"] = H.gget(sd, "^NKG", "$meta", "invalidated")
    s["ni_defined_after_erase"] = H.defined(sd, "^NKG", "$NI")
    return s


def after_p1a(sd):
    return {"ni_lp4": H.gget(sd, "^NKG", "$NI", "lp|4"), "kg_out_lp4": H.defined(sd, "^KG", "out", 0, "lp|4", "R", "lp|1"),
            "nodeCount": H.gget(sd, "^NKG", "$meta", "nodeCount")}


def after_p1b(sd):
    return {"invalidated": H.gget(sd, "^NKG", "$meta", "invalidated"), "ni_defined": H.defined(sd, "^NKG", "$NI"),
            "ensure": str(sd.o.classMethodValue("Graph.KG.TraversalBuild", "EnsureNKG"))}


def kcore(sd):
    return str(sd.o.classMethodValue("Graph.KG.Communities", "KCoreJson", 100))[:300]


def both_waiting(obs, sides, done):
    """release once X1 and X2 are both parked (state names a lock wait) or one has returned"""
    st = [L.proc_state(obs.c, s.c.pid) for t, s in sides.items()]
    return all("LOCK" in (x.get("state") or "").upper() for x in st) or bool(done)


def p2(out: Path) -> dict:
    """Sequential, deterministic: no lock is held by a probe."""
    A, B, obs = H.Side(), H.Side(), H.Side()
    res = {"probe": "P2-interning-rollback", "pids": {"A": A.c.pid, "B": B.c.pid, "obs": obs.c.pid}}
    try:
        L.reset(obs.c)
        for n in ("lp|a", "lp|b", "lp|c", "lp|d", "lp|e", "lp|f"):
            obs.e.create_node(n)
        obs.e.create_edge("lp|x", "R", "lp|y")
        obs.c.conn.commit()
        res["sync"] = str(obs.e.sync())[:200]
        obs.c.conn.commit()
        res["indexed"] = str(obs.o.classMethodValue("Graph.KG.Adjacency", "Indexed"))
        res["pre"] = {"li_LPNEW": H.gget(obs, "^NKG", "$LI", "LPNEW"), "labelCount": H.gget(obs, "^NKG", "$meta", "labelCount"),
                      "nkg_built": H.defined(obs, "^NKG", "$meta", "nodeCount"), "ensure": str(obs.o.classMethodValue(
                          "Graph.KG.TraversalBuild", "EnsureNKG"))}
        m0 = H.journal.mark()
        A.c.sql("START TRANSACTION")
        res["A_tlevel"] = L.tlevel(A.c)
        res["A_create_edge"] = L.call(lambda: A.e.create_edge("lp|a", "LPNEW", "lp|b"))
        k = H.gget(obs, "^NKG", "$LI", "LPNEW")
        res["after_A_uncommitted"] = {"li_LPNEW": k, "ls_k": H.gget(obs, "^NKG", "$LS", k) if k else None,
                                      "labelCount": H.gget(obs, "^NKG", "$meta", "labelCount")}
        res["B_create_edge"] = L.call(lambda: B.e.create_edge("lp|c", "LPNEW", "lp|d"))
        B.c.conn.commit()
        ic, idd = H.gget(obs, "^NKG", "$NI", "lp|c"), H.gget(obs, "^NKG", "$NI", "lp|d")
        res["after_B_committed"] = {"ni_c": ic, "ni_d": idd,
                                    "B_row_under_k": H.defined(obs, "^NKG", -1, int(ic), -(int(k) + 1), int(idd))
                                    if (ic and idd and k) else None}
        A.c.sql("ROLLBACK")
        res["A_tlevel_after_rollback"] = L.tlevel(A.c)
        post = {"li_LPNEW": H.gget(obs, "^NKG", "$LI", "LPNEW"), "ls_k": H.gget(obs, "^NKG", "$LS", k) if k else None,
                "labelCount": H.gget(obs, "^NKG", "$meta", "labelCount"),
                "B_row_under_k": H.defined(obs, "^NKG", -1, int(ic), -(int(k) + 1), int(idd)) if (ic and idd and k) else None,
                "kg_out_B": H.defined(obs, "^KG", "out", 0, "lp|c", "LPNEW", "lp|d"),
                "kg_out_A": H.defined(obs, "^KG", "out", 0, "lp|a", "LPNEW", "lp|b"),
                "rdf_edges_B": int(obs.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s='lp|c' AND p='LPNEW'")[0][0]),
                "invalidated": H.gget(obs, "^NKG", "$meta", "invalidated"),
                "ensure": str(obs.o.classMethodValue("Graph.KG.TraversalBuild", "EnsureNKG"))}
        try:
            exp = str(obs.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "ExportAdjacencyWithPreds", "", 0))
            post["export_lines_for_lp_c"] = [ln for ln in exp.replace("\r", "").split("\n") if "lp|c" in ln][:5]
            post["export_names_LPNEW"] = "LPNEW" in exp
        except Exception as ex:  # noqa: BLE001
            post["export_error"] = str(ex)[:300]
        res["after_A_rollback"] = post
        # C: a third writer of the same label now
        res["C_create_edge"] = L.call(lambda: obs.e.create_edge("lp|e", "LPNEW", "lp|f"))
        obs.c.conn.commit()
        k2 = H.gget(obs, "^NKG", "$LI", "LPNEW")
        res["after_C"] = {"li_LPNEW": k2, "same_index_as_B": k2 == k, "ls_k2": H.gget(obs, "^NKG", "$LS", k2) if k2 else None}
        recs = H.journal.records_since(m0, dbs={L.DB}, pids={A.c.pid, B.c.pid})
        res["journal"] = {"A_nkg_dict_nodes": sorted({r["g"][:80] for r in recs if r["p"] == A.c.pid and
                                                       ("$LI" in r["g"] or "$LS" in r["g"])}),
                          "B_nkg_dict_nodes": sorted({r["g"][:80] for r in recs if r["p"] == B.c.pid and
                                                       ("$LI" in r["g"] or "$LS" in r["g"])}),
                          "B_nkg_rows": sorted({r["g"][:80] for r in recs if r["p"] == B.c.pid and r["g"].startswith("^NKG(-1")})}
        v = res["after_A_rollback"]
        res["violated"] = bool(v.get("B_row_under_k")) and not v.get("li_LPNEW") and v.get("ensure") == "1"
    finally:
        try:
            L.reset(obs.c)
        except Exception as ex:  # noqa: BLE001
            res["final_reset_error"] = str(ex)[:200]
        for s in (A, B, obs):
            s.close()
    return res


def probes():
    return [
        dict(name="P1a-writer-during-NKGBuild", lock=NKGB, hold=3.0, setup=setup_triangle,
             ops=[("X", 0.0, lambda sd: sd.e.create_edge("lp|4", "R", "lp|1"), False)], after=after_p1a,
             expect="X finishes while ^IVG.NKGBuild is held and asks no ^IVG.NKGBuild lock; it interns lp|4"),
        dict(name="P1b-two-readers-EnsureNKG", lock=NKGB, hold=4.0, setup=setup_invalidated,
             ops=[("X1", 0.0, kcore, False), ("X2", 0.5, kcore, False)], after=after_p1b,
             expect="X1 and X2 wait for ^IVG.NKGBuild in EnsureNKG (TraversalBuild.cls:410); after release exactly one "
                    "rewrites ^NKG (journal), the other writes no ^NKG record; mark cleared"),
    ]


def main() -> int:
    out = Path(sys.argv[1])
    only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else []
    c = L.conn()
    print("engine:", L.version(c), "namespace", c.namespace, flush=True)
    c.close()
    results = []
    for p in probes():
        if only and p["name"] not in only:
            continue
        r = H.run(**p)
        results.append(r)
        L.dump(out / f"{p['name']}.json", r)
        print(json.dumps({"probe": r["probe"], "ops": r.get("ops"), "returned_before_release": r.get("returned_before_release"),
                          "state_last": (r.get("state_while_held") or [None])[-1], "locks": r.get("locks_while_held"),
                          "after": r.get("after"),
                          "journal": {k: {"before": v["before_release"], "roots": v["roots_total"],
                                          "nkg_nodes": [n for n in v["nodes_before_release"] if "NKG" in n][:5]}
                                      for k, v in r.get("journal", {}).items()}},
                         default=str)[:3000], flush=True)
    if not only or "P2-interning-rollback" in only:
        r = p2(out)
        results.append(r)
        L.dump(out / "P2-interning-rollback.json", r)
        print(json.dumps(r, default=str)[:3000], flush=True)
    L.dump(out / "nkg_probes.json", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
