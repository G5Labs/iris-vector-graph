#!/usr/bin/env python3
"""F3: the ledger's delete_rel of one of two parallel edges, in multigraph mode (spec 234, spec 252 FR-001).

L1 (model: graph_structure.rs §3, layout/theorem_repaired_delete_rel_keeps_layout): in a multigraph-mode graph the
Adjacency Index of a triple is a function of its live rows — after deleting one of two parallel relationships, one row
remains, and the triple must be a bare leaf (spec 234 FR-004: byte-identical to a single edge), its source's degree
1, the target still a neighbour, verify_graph clean.

Model prediction (witness_ledger_delete_rel_drops_survivor_indexed / ..._non_indexed): LedgerApply.DeleteRelInternal
deletes the row FindEdge picked (LedgerApply.cls:678) — the index collapses the triple to the survivor's bare leaf —
and then calls Adjacency.Remove on the whole triple because its leaf exists (689), so the survivor's row has no
adjacency entry and degree 0.

Public entry points only: engine.set_multigraph, engine.create_node, Cypher CREATE (the one writer that makes parallel
edges at this pin; create_edge returns False for an existing triple, FR-007 open), engine.ledger.commit with a
delete_relationship tuple reference, engine.verify_graph. Globals and Graph.KG.Adj.Degree/Count are read to observe.
Runs once for the default graph and once for a named graph. Writes nothing outside this arm's IRIS.
"""
from __future__ import annotations

from graph_structure_common import (adj_count, adj_degree, connect, engine, ensure_schema, err, finish, index_kind,
                                    reset, sql_all, triple_layout)

NAME = "graph_structure_parallel_delete_rel"
P = "G5PS_T"
CASES = [(None, 0), ("g5ps_named", "g5ps_named")]  # (graph name, ^KG key = GraphKey.ForIndex(name), from L1 of §1)


def rows(conn, s, p, o, graph):
    return sql_all(conn, "SELECT edge_id, ekey, graph_id FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? "
                         "AND COALESCE(graph_id, '') = ? ORDER BY ekey", [s, p, o, graph or ""])


def expected_after(n_rows_after: int) -> dict:
    """L1: the layout of n live rows in a multigraph-mode graph, and what degree and neighbours read from it."""
    if n_rows_after == 0:
        return {"present": False, "children": 0, "hash": None, "degree": 0}
    if n_rows_after == 1:
        return {"present": True, "children": 0, "hash": None, "degree": 1}
    return {"present": True, "children": n_rows_after, "hash": n_rows_after, "degree": n_rows_after}


def judge(case: dict) -> tuple[str, str]:
    if case.get("setup_error") or case.get("rows_before_n") != 2:
        return "INCONCLUSIVE", f"setup did not produce two parallel rows: {case.get('setup_error') or case.get('rows_before_n')}"
    if case.get("ledger_error"):
        # a refusal is acceptable only when nothing changed
        if case.get("rows_after_n") == 2 and case["layout_after"]["children"] == case["layout_before"]["children"]:
            return "OBSERVED_AS_EXPECTED", "the ledger refused delete_rel on a parallel triple and changed nothing"
        return "OBSERVED_DEFECT", "the ledger reported an error and changed rows or adjacency"
    n = case.get("rows_after_n")
    if n != 1:
        return "INCONCLUSIVE", f"delete_rel left {n} rows, not 1"
    exp = expected_after(n)
    lay = case["layout_after"]
    present = isinstance(lay.get("data"), int) and lay["data"] > 0
    got = {"present": present, "children": len(lay["children"]),
           "hash": None if lay["hash"] is None else int(lay["hash"]), "degree": case.get("degree_after")}
    case["expected_after"] = exp
    case["observed_after"] = got
    if got == exp and case.get("count_after") == exp["degree"]:
        return "OBSERVED_AS_EXPECTED", "the survivor keeps a bare leaf and degree 1"
    return "OBSERVED_DEFECT", f"one row remains but the index reads {got} (expected {exp}; recount {case.get('count_after')})"


def run_case(eng, native, conn, graph, gkey) -> dict:
    tag = graph or "default"
    s, o = f"g5ps:{tag}:a", f"g5ps:{tag}:b"
    case = {"graph": graph, "gkey": gkey, "s": s, "p": P, "o": o}
    try:
        eng.set_multigraph(graph, True)
        case["is_multigraph"] = eng.is_multigraph(graph)
        eng.create_node(s, graph=graph)
        eng.create_node(o, graph=graph)
        use = f"USE GRAPH '{graph}' " if graph else ""
        q = f"{use}MATCH (a {{id: '{s}'}}), (b {{id: '{o}'}}) CREATE (a)-[:{P}]->(b)"
        eng.execute_cypher(q, {})
        eng.execute_cypher(q, {})
    except Exception as e:  # noqa: BLE001
        case["setup_error"] = err(e)
    before = rows(conn, s, P, o, graph)
    case["rows_before"] = before
    case["rows_before_n"] = len(before)
    case["layout_before"] = triple_layout(native, gkey, s, P, o)
    case["degree_before"] = adj_degree(native, gkey, s)
    case["count_before"] = adj_count(native, gkey, s)
    try:
        case["verify_before"] = eng.verify_graph(graph)
    except Exception as e:  # noqa: BLE001
        case["verify_before"] = err(e)
    if case.get("setup_error") or len(before) != 2:
        return case
    from iris_vector_graph.ledger import Changeset

    cs = Changeset(actor="g5-probe", actor_type="system", message="graph_structure F3 probe")
    cs.delete_relationship((s, P, o, graph) if graph else (s, P, o))
    try:
        res = eng.ledger.commit(cs)
        case["ledger_result"] = {"revision": str(getattr(res.revision, "revision_id", res.revision)), "replayed": res.replayed}
    except Exception as e:  # noqa: BLE001
        case["ledger_error"] = err(e)
    after = rows(conn, s, P, o, graph)
    case["rows_after"] = after
    case["rows_after_n"] = len(after)
    case["layout_after"] = triple_layout(native, gkey, s, P, o)
    case["degree_after"] = adj_degree(native, gkey, s)
    case["count_after"] = adj_count(native, gkey, s)
    try:
        case["neighbours_cypher"] = [list(r) for r in eng.execute_cypher(
            (f"USE GRAPH '{graph}' " if graph else "") + f"MATCH (a {{id: '{s}'}})-[r:{P}]->(b) RETURN b.id", {}).rows]
    except Exception as e:  # noqa: BLE001
        case["neighbours_cypher"] = err(e)
    try:
        case["verify_after"] = eng.verify_graph(graph)
    except Exception as e:  # noqa: BLE001
        case["verify_after"] = err(e)
    return case


def self_check() -> dict:
    """The decisive observed fields must change the verdict (guidance: change an observed field that decides it)."""
    base = {"rows_before_n": 2, "rows_after_n": 1, "degree_after": 0, "count_after": 0,
            "layout_before": {"children": ["0", "1"]},
            "layout_after": {"data": 0, "children": [], "hash": None}}
    good = dict(base, degree_after=1, count_after=1, layout_after={"data": 1, "children": [], "hash": None})
    v_bad, _ = judge(dict(base))
    v_good, _ = judge(dict(good))
    return {"defect_case": v_bad, "fixed_case": v_good, "discriminates": v_bad == "OBSERVED_DEFECT" and v_good == "OBSERVED_AS_EXPECTED"}


def main() -> None:
    obs = {"probe": NAME}
    conn, native = connect()
    eng = engine(conn)
    obs["schema"] = ensure_schema(eng)
    reset(eng, native)
    obs["adjacency_index_kind"] = index_kind(native)
    try:
        eng.ledger.enable()
    except Exception as e:  # noqa: BLE001
        obs["ledger_enable_error"] = err(e)
    cases = []
    for graph, gkey in CASES:
        c = run_case(eng, native, conn, graph, gkey)
        c["verdict"], c["reason"] = judge(c)
        cases.append(c)
    obs["cases"] = cases
    # F7 (secondary): verify_graph on a graph holding two parallel rows of one triple, before the delete
    obs["f7_verify_before"] = [c.get("verify_before") for c in cases]
    sc = self_check()
    verdicts = [c["verdict"] for c in cases]
    if "OBSERVED_DEFECT" in verdicts:
        v, why = "OBSERVED_DEFECT", "; ".join(f"{c['graph'] or 'default'}: {c['reason']}" for c in cases)
    elif all(x == "OBSERVED_AS_EXPECTED" for x in verdicts):
        v, why = "OBSERVED_AS_EXPECTED", "both graphs keep the survivor's adjacency and degree"
    else:
        v, why = "INCONCLUSIVE", "; ".join(f"{c['graph'] or 'default'}: {c['reason']}" for c in cases)
    if not sc["discriminates"]:
        v, why = "INCONCLUSIVE", f"verdict self-check failed: {sc}"
    for graph, _ in CASES:
        try:
            eng.set_multigraph(graph, False)
        except Exception:
            pass
    finish(NAME, v, why, obs, sc)


if __name__ == "__main__":
    main()
