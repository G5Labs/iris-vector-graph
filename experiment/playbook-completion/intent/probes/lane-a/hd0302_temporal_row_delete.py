"""HD-0302 probe: may delete_edge(s, p, o, graph=g) remove the structural row a surviving temporal edge implies?

Contract under test (the invariant reading): CONTEXT.md:66-73 "Every Temporal Edge implies a Structural Edge for the
same triple in the same graph (unless its predicate is a Temporal-only predicate) ... Removing the triple's last
timestamp removes that Structural Edge only while it is still marked"; ADR-0009 Decision (accepted) and its Context
(an edge with timestamps but no row "vanishes from every reader of the Adjacency Index although it still exists").
Competing evidence: tests/e2e/test_254_purge_e2e.py:322-327 (7374d3b4, 2026-10-22) runs delete_edge on a temporal-only
triple and then expects the purge to delete its 1 timestamp, i.e. it accepts a timestamp living on without a row.

Cases, probe-private graph ia-0302 (structural predicate, not opted out):
  A. marked row  : create_edge_temporal(a, P, b, T)                       -> delete_edge(a, P, b)
  B. adopted row : create_edge_temporal(c, P, d, T); create_edge(c, P, d) -> delete_edge(c, P, d)
Oracle after each delete: does the triple still have an rdf_edges row / ^KG("out") entry while its timestamp is still
returned by get_edges_in_window?
  row kept (or re-marked) while a timestamp survives -> invariant reading holds (options b/d)
  row gone, timestamp kept                            -> as built option (a): invariant broken (verdict fail)
  row and timestamp gone                              -> option (c)
"""
from __future__ import annotations

import _common as C

G = "ia-0302"
P = "IA0302P"
T = 1_790_000_000


def state(c, e, s, o):
    rows = c.sql("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?",
                 s, P, o, G)
    ts = [x["ts"] for x in e.get_edges_in_window(source=s, predicate=P, start=T - 10, end=T + 10, graph=G)
          if x.get("o") == o]
    return {"rows": [r[0] for r in rows], "kg_out": int(c.o.isDefined("^KG", "out", G, s, P, o) or 0),
            "timestamps": ts}


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    results = {}
    try:
        e.erase_graph(G)
        C.obs(step="policy", structural=e.get_temporal_structural(P, graph=G))
        # A: marked row
        e.create_edge_temporal("ia0302:a", P, "ia0302:b", timestamp=T, graph=G)
        C.obs(case="A", when="before delete_edge", **state(c, e, "ia0302:a", "ia0302:b"))
        e.delete_edge("ia0302:a", P, "ia0302:b", graph=G)
        results["A"] = state(c, e, "ia0302:a", "ia0302:b")
        C.obs(case="A", when="after delete_edge", **results["A"])
        # B: adopted (explicit) row
        e.create_edge_temporal("ia0302:c", P, "ia0302:d", timestamp=T, graph=G)
        e.create_edge("ia0302:c", P, "ia0302:d", graph=G)
        C.obs(case="B", when="before delete_edge", **state(c, e, "ia0302:c", "ia0302:d"))
        e.delete_edge("ia0302:c", P, "ia0302:d", graph=G)
        results["B"] = state(c, e, "ia0302:c", "ia0302:d")
        C.obs(case="B", when="after delete_edge", **results["B"])

        broken = [k for k, v in results.items() if v["timestamps"] and not v["rows"]]
        if broken:
            C.verdict("fail", f"cases {broken}: delete_edge removed the structural row while the triple's timestamp "
                              "survives (CONTEXT/ADR-0009 implication broken; as-built option a)")
        elif all(not v["timestamps"] and not v["rows"] for v in results.values()):
            C.verdict("pass", "delete_edge removed row and timestamps together (option c)")
        else:
            C.verdict("pass", "the row survives while a timestamp survives")
    finally:
        e.erase_graph(G)
        left = e.get_edges_in_window(source="", predicate=P, start=T - 10, end=T + 10, graph=G)
        C.obs(step="cleanup", temporal_left=len(left),
              rows_left=c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", G),
              nodes_left=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", G))
        c.close()


if __name__ == "__main__":
    main()
