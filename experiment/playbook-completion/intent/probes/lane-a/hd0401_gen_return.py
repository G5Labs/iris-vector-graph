"""HD-0401 probe: can a source's degree generation return to a value it held before an erase?

Contract cited:
- ADR-0012 Decision/Consequences (docs/adr/0012-...md): a cached degree is valid when its generation equals
  ^KG("gen", g, s); "Every adjacency write must bump the generation and hold the shared lock".
- Spec 252 FR-004 (Draft): "Every index change MUST move the source's degree generation (ADR-0012)".
- Working property (decisions.md HD-0401): "invalidation can never make an old degree-cache value valid again",
  i.e. a generation never returns to a value an in-flight reader may have read.
- Counter-source: Adj.cls:46-48 comment ("Graph.KG.Adjacency kills the generation when it erases a source, so a
  counter can restart at a value an old entry carries") and the degree-cache spike README ("bump ... or kill the
  cache subtree").

Oracle: write edges for source S in a probe-private graph, read gen G1 (read-only Native API $Get); erase the
source (delete_node -> Adjacency.RemoveSource) or the graph (erase_graph -> Adjacency.RemoveGraph); rewrite the same
edges; read gen G2.
- G2 == G1 after an erase (generation returned to an earlier value): as-built option A (kill). An in-flight reader
  that read G1 before the erase would validate a count taken across the erase. Violates the working property.
- G2 > G1 (monotone): options B/C (step or epoch).
Also records the public degree answer after the rewrite (must equal the true count; the probe does not inject a
stale entry, so this only checks the single-process path is right).
"""
from __future__ import annotations

import _common as C

G = "ia-0401"
S, T1, T2 = "ia0401:s", "ia0401:t1", "ia0401:t2"


def gen(c) -> int:
    v = c.o.get("^KG", "gen", G, S)
    return 0 if v is None or v == "" else int(v)


def degc_defined(c) -> int:
    return int(c.o.isDefined("^KG", "degc", G, S))


def write_edges(e) -> None:
    for n in (S, T1, T2):
        e.create_node(n, graph=G)
    e.create_edge(S, "R", T1, graph=G)
    e.create_edge(S, "R", T2, graph=G)


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    try:
        e.erase_graph(G)
        indexed = int(c.call("Graph.KG.Adjacency", "Indexed"))
        C.obs(step="setup", adjacency_indexed=indexed, gen=gen(c))
        returned = []

        write_edges(e)
        g1 = gen(c)
        d1 = int(c.call("Graph.KG.Adj", "Degree", G, S, ""))
        C.obs(step="written-1", gen=g1, degree=d1, degc_defined=degc_defined(c))

        # erase path 1: the whole graph (Eraser -> Adjacency.RemoveGraph)
        n = e.erase_graph(G)
        C.obs(step="erase_graph", removed=n, gen_after=gen(c), gen_defined=int(c.o.isDefined("^KG", "gen", G, S)),
              degc_defined=degc_defined(c))
        write_edges(e)
        g2 = gen(c)
        d2 = int(c.call("Graph.KG.Adj", "Degree", G, S, ""))
        C.obs(step="rewritten-after-erase_graph", gen=g2, degree=d2)
        returned.append(("erase_graph", g1, g2))

        # erase path 2: the source node (delete_node -> Adjacency.RemoveNode/RemoveSource)
        g3 = gen(c)
        ok = e.delete_node(S, graph=G)
        C.obs(step="delete_node", ok=ok, gen_after=gen(c), gen_defined=int(c.o.isDefined("^KG", "gen", G, S)))
        e.create_node(S, graph=G)
        e.create_edge(S, "R", T1, graph=G)
        e.create_edge(S, "R", T2, graph=G)
        g4 = gen(c)
        d4 = int(c.call("Graph.KG.Adj", "Degree", G, S, ""))
        C.obs(step="rewritten-after-delete_node", gen_before_delete=g3, gen=g4, degree=d4)
        returned.append(("delete_node", g3, g4))

        hits = [r for r in returned if r[2] <= r[1] and r[1] > 0]
        C.obs(step="summary", pairs=returned, generation_returned_to_earlier_value=[r[0] for r in hits],
              degrees_correct=(d1 == 2 and d2 == 2 and d4 == 2))
        if hits:
            C.verdict("fail", "generation returned to a value held before the erase on "
                      + ",".join(r[0] for r in hits) + " (kill, not step): ABA precondition for F-0401 is reachable")
        else:
            C.verdict("pass", "generation strictly advanced across erase and rewrite")
    finally:
        try:
            e.erase_graph(G)
        finally:
            c.close()


if __name__ == "__main__":
    main()
