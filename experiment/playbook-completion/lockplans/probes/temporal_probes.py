#!/usr/bin/env python3
"""Module 05 lock plans, live on AUDITD (gate 3.5-lockplans).

    locks.sh iris python temporal_probes.py OUT_DIR [--only NAME ...]

No temporal class takes a lock of its own (draft $RUN_DIR/lockplans/drafts/05.md section 1; footprints/05.json): the
only lock on these paths is the shared ^IVG.AdjW(graph) of the adjacency row writers (Adjacency.cls:61-74, 63). A
probe connection holding ^IVG.AdjW(gk) exclusively parks a temporal writer at that lock (for less than its 5 s
timeout, after which it would go on fail-open), which opens the windows between the writer's unlocked steps. Each
probe has a serial control (the same two operations in sequence, no hold) measured live.

  P1 (LP-05-3): insert (s,P,o2,1001) parked between its tout/bucket writes (TemporalIndex.cls:97-102) and its
      aggregate writes (:117-125); a delete of (s,P,o1,1000) in the same bucket rebuilds the bucket aggregate
      (:463-485) meanwhile. Oracle TMP-B4.2 / TMP-B8 (aggregate equals the surviving edges).
  P2 (LP-05-6): delete of a triple's only time parked inside its row retraction (:334-337, Adjacency.cls:628-636);
      an insert of a new time of the same triple meanwhile trusts ^KG("out") and skips its row (Adjacency.cls:577).
      Oracle TMP-B2 (a temporal edge's triple has its marked row).
  P3a (LP-05-5a): purge_raw_before parked in its row retraction (:983-1016, Adjacency.cls:674); an insert outside
      the purged range meanwhile. Oracle TMP-B9.4/9.5, TMP-B2.
  P3b (LP-05-5b): two overlapping purges. Oracle TMP-B9.13 (a marked row only while a timestamp remains).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpcommon as L  # noqa: E402
import holdprobe as H  # noqa: E402

G = "lp05"


def gk(side):
    return str(side.o.classMethodValue("Graph.KG.GraphKey", "ForIndex", G))


def cet(s, p, o, ts, w=1.0):
    return lambda sd: sd.e.create_edge_temporal(s, p, o, timestamp=ts, weight=w, graph=G)


def det(s, p, o, ts):
    return lambda sd: sd.e.delete_edge_temporal(s, p, o, ts, graph=G)


def purge(ts_end, ts_start=0, retire=False):
    return lambda sd: str(sd.e.purge_raw_before(ts_end, ts_start=ts_start, graph=G, retire_bare_nodes=retire))


def window(sd, s="s", p="P", a=0, b=100000):
    return sorted([[str(e.get("target") or e.get("o") or e.get("dst")), int(e.get("ts") or e.get("timestamp") or 0)]
                   for e in sd.e.get_edges_in_window(s, p, a, b, graph=G)])


def rows(sd, s, p, o):
    return int(sd.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?",
                        s, p, o, G)[0][0])


def node_rows(sd, *ids):
    return {i: int(sd.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ? AND graph_id = ?", i, G)[0][0])
            for i in ids}


def agg(sd, metric, a, b):
    try:
        return str(sd.e.get_temporal_aggregate("s", "P", metric, a, b, graph=G))
    except Exception as ex:  # noqa: BLE001
        return f"<{type(ex).__name__}: {str(ex)[:120]}>"


def setup_of(*writes):
    def f(sd):
        out = [str(w(sd)) for w in writes]
        sd.c.conn.commit()
        return {"writes": out, "gk": gk(sd), "indexed": str(sd.o.classMethodValue("Graph.KG.Adjacency", "Indexed"))}
    return f


def after_p1(sd):
    return {"bucket_count_900_1199": agg(sd, "count", 900, 1199), "bucket_sum_900_1199": agg(sd, "sum", 900, 1199),
            "cut_count_901_1199": agg(sd, "count", 901, 1199), "cut_sum_901_1199": agg(sd, "sum", 901, 1199),
            "edges_900_1199": window(sd, a=900, b=1199), "edges_all": window(sd)}


def after_triple(o, extra_nodes=()):
    def f(sd):
        k = gk(sd)
        return {"edges_all": window(sd), f"rows_s_P_{o}": rows(sd, "s", "P", o),
                f"kg_out_s_P_{o}": H.defined(sd, "^KG", "out", k, "s", "P", o),
                "nodes": node_rows(sd, "s", o, *extra_nodes)}
    return f


def after_p3b(sd):
    k = gk(sd)
    return {"edges_all": window(sd), **{f"rows_s_P_{o}": rows(sd, "s", "P", o) for o in ("t", "u", "v")},
            **{f"kg_out_s_P_{o}": H.defined(sd, "^KG", "out", k, "s", "P", o) for o in ("t", "u", "v")}}


def adjw(sd_unused=None):
    return ("^IVG.AdjW", (G,))


def probes():
    p1_setup = setup_of(cet("s", "P", "o1", 1000, 1.0), cet("s", "P", "o1", 2000, 1.0))
    p1_ops_held = [("X", 0.0, cet("s", "P", "o2", 1001, 5.0), False), ("Y", 1.0, det("s", "P", "o1", 1000), False)]
    p1_ops_serial = [("X", 0.0, cet("s", "P", "o2", 1001, 5.0), False), ("Y", 1.5, det("s", "P", "o1", 1000), False)]
    p2_setup = setup_of(cet("s", "P", "o", 1000))
    p2_held = [("X", 0.0, det("s", "P", "o", 1000), False), ("W", 1.0, cet("s", "P", "o", 5000), False)]
    p2_serial = [("X", 0.0, det("s", "P", "o", 1000), False), ("W", 1.5, cet("s", "P", "o", 5000), False)]
    p3a_setup = setup_of(cet("s", "P", "o", 1000), cet("s", "P", "u", 1100))
    p3a_held = [("X", 0.0, purge(1500, retire=True), False), ("W", 1.0, cet("s", "P", "o", 9000), False)]
    p3a_serial = [("X", 0.0, purge(1500, retire=True), False), ("W", 2.0, cet("s", "P", "o", 9000), False)]
    p3b_setup = setup_of(cet("s", "P", "t", 20), cet("s", "P", "t", 150), cet("s", "P", "u", 30), cet("s", "P", "v", 160))
    p3b_held = [("X1", 0.0, purge(100, 0), False), ("X2", 0.5, purge(200, 50), False)]
    p3b_serial = [("X1", 0.0, purge(100, 0), False), ("X2", 2.0, purge(200, 50), False)]
    lk = ("^IVG.AdjW", (G,))
    return [
        dict(name="P1-insert-vs-bucket-rebuild", lock=lk, hold=3.0, setup=p1_setup, ops=p1_ops_held, after=after_p1,
             expect="as built: whole-bucket count 2 / sum 10 against one edge (o2, w 5) in [900,1199]; serial 1 / 5"),
        dict(name="P1-serial-control", lock=None, hold=3.0, setup=p1_setup, ops=p1_ops_serial, after=after_p1,
             expect="serial insert then delete: bucket count 1, sum 5"),
        dict(name="P2-delete-last-time-vs-insert", lock=lk, hold=3.0, setup=p2_setup, ops=p2_held,
             after=after_triple("o"),
             expect="as built: the ts=5000 edge is kept with 0 rows and no ^KG(out) entry; serial: 1 row, out defined"),
        dict(name="P2-serial-control", lock=None, hold=3.0, setup=p2_setup, ops=p2_serial, after=after_triple("o")),
        dict(name="P3a-purge-vs-insert-outside-range", lock=lk, hold=3.0, setup=p3a_setup, ops=p3a_held,
             after=after_triple("o", ("u",)),
             expect="as built: tout(9000,s,P,o) kept with 0 rows, no ^KG(out), nodes s and o retired; serial: row and "
                    "both nodes stay"),
        dict(name="P3a-serial-control", lock=None, hold=3.5, setup=p3a_setup, ops=p3a_serial,
             after=after_triple("o", ("u",))),
        dict(name="P3b-two-overlapping-purges", lock=lk, hold=3.0, setup=p3b_setup, ops=p3b_held, after=after_p3b,
             expect="as built: t has no timestamp left but keeps its marked row and ^KG(out); serial: t's row retracted"),
        dict(name="P3b-serial-control", lock=None, hold=3.5, setup=p3b_setup, ops=p3b_serial, after=after_p3b),
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
                          "state_last": (r.get("state_while_held") or [None])[-1], "after": r.get("after"),
                          "journal_roots_before_release": {k: v["roots_before_release"] for k, v in r.get("journal", {}).items()}},
                         default=str)[:2500], flush=True)
    L.dump(out / "temporal_probes.json", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
