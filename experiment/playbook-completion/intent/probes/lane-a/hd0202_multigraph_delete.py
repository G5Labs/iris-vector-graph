"""HD-0202 probe: in a multigraph, does delete_edge(s, p, o, graph=g) remove one parallel edge or all of them?

Sources the outcome is compared with:
  - docs/USER_GUIDE.md:462 "`delete_edge(s, p, o, graph=...)` deletes one edge" (single-edge wording);
  - specs/234-multigraph-parallel-edges/plan.md:160-162 (128007c0, 2026-09-26): "With no `edge_id`, it deletes every
    parallel edge of the triple, which is today's meaning" (the planned `edge_id=` argument, T033, is unchecked);
  - spec 234 Edge Cases / FR-013: a ledger tuple ref to a triple with several live edges fails `ambiguous_tuple`.
Fixture: probe-private graph ia-0202 in multigraph mode; two parallel ia0202:a -[IA0202P]-> ia0202:b edges. The direct
API is tried first (spec 234 FR-007: in a multigraph "create_edge MUST always create a new edge"; T033 is unchecked);
the parallel edges are then made by Cypher CREATE, the path spec 234 says shipped in 4.1.0.
Oracle: rows of the triple after one delete_edge call:
  0 -> triple-wide delete (plan.md reading, as designed);   1 -> per-edge delete (USER_GUIDE "one edge");
  raises an ambiguity error with 2 left -> refusal (option b).
Also checks the ^KG out entry agrees with the rows, and that delete_edge accepts no edge_id=.
Verdict: pass if the outcome is the triple-wide delete that spec 234's plan names (the only design statement for the
direct API); the USER_GUIDE wording is recorded as a contradiction either way.
"""
from __future__ import annotations

import _common as C

G = "ia-0202"
S, P, O = "ia0202:a", "IA0202P", "ia0202:b"


def rows(c):
    return c.sql("SELECT edge_id, ekey FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?",
                 S, P, O, G)


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    try:
        e.erase_graph(G)
        e.set_multigraph(G, True)
        C.obs(step="mode", multigraph=e.is_multigraph(G))
        e.create_node(S, graph=G)
        e.create_node(O, graph=G)
        r1, r2 = e.create_edge(S, P, O, graph=G), e.create_edge(S, P, O, graph=G)
        C.obs(step="create_edge x2 (FR-007)", returns=[r1, r2], rows=rows(c))
        if len(rows(c)) < 2:
            res = e.execute_cypher(f"USE GRAPH '{G}' MATCH (a {{id: '{S}'}}), (b {{id: '{O}'}}) CREATE (a)-[:{P}]->(b)")
            C.obs(step="cypher CREATE", error=res.get("error") if isinstance(res, dict) else None)
        before = rows(c)
        C.obs(step="created", rows=before)
        try:
            e.delete_edge(S, P, O, graph=G, edge_id=before[0][0])
            edge_id_arg = "accepted"
        except TypeError as exc:
            edge_id_arg = f"TypeError: {exc}"
        C.obs(step="edge_id= argument", outcome=edge_id_arg)
        outcome = None
        try:
            ret = e.delete_edge(S, P, O, graph=G)
            C.obs(step="delete_edge", returned=ret)
        except Exception as exc:  # noqa: BLE001
            outcome = f"raised {type(exc).__name__}: {exc}"
        after = rows(c)
        out_entry = c.o.isDefined("^KG", "out", G, S, P, O)
        C.obs(step="after", rows=after, kg_out_defined=out_entry, raised=outcome)
        if outcome and len(after) == 2:
            C.verdict("pass", "refused the ambiguous delete (option b)")
        elif len(before) == 2 and len(after) == 0 and not int(out_entry or 0):
            C.verdict("pass", "one delete_edge call removed both parallel edges (triple-wide, spec 234 plan.md:160-162; "
                              "USER_GUIDE 'deletes one edge' does not describe it); no edge_id= argument")
        elif len(after) == 1:
            C.verdict("pass", "per-edge delete")
        else:
            C.verdict("fail", f"before={len(before)} after={len(after)} kg_out={out_entry} raised={outcome}")
    finally:
        e.erase_graph(G)
        C.obs(step="cleanup", multigraph_after_erase=e.is_multigraph(G),
              rows_left=c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", G))
        if e.is_multigraph(G):
            e.set_multigraph(G, False)
        c.close()


if __name__ == "__main__":
    main()
