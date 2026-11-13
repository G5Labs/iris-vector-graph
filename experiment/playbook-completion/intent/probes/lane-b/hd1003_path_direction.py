"""HD-1003 probe: what the shortest-path routines answer for a direction they do not walk.

Namespace AUDITIB, default graph, one edge ib1_sp_x -R-> ib1_sp_y. SHARED lane lock.
Ground truth: walking "in" (against the edges) from y reaches x in 1 hop; walking "in" from x reaches nothing.
Oracles:
  - Maintainer statement, TraversalPaths.cls:348-349 (4.6.0 round 3): answering an unsupported direction "with no
    path, as if there were none" was a defect; DijkstraJson/DijkstraCost now throw through CheckDirection.
  - ShortestLength's own doc (TraversalPaths.cls:115): direction "out" or "both" (a precondition, unchecked).
  - Callers normalize "in" (iris_sql_store.py:2196-2207, query.py:3618-3625).
  - IRISGraphStore.shortest_path_length's docstring (iris_sql_store.py:2166-2167): the length is "what
    execute_shortest_path's paths' length is" (execute_shortest_path reverses "in", :2196-2207).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402

P = "ib1_sp_"
TP = "Graph.KG.TraversalPaths"


def attempt(label, fn):
    try:
        out = fn()
    except Exception as exc:  # noqa: BLE001
        out = f"RAISED {type(exc).__name__}: {str(exc)[:160]}"
    print(f"OBS {label}: {out}")
    return out


def main():
    c = Conn("AUDITIB")
    eng = IRISGraphEngine(c.conn, namespace="AUDITIB", embedding_dimension=4)
    eng.delete_nodes_by_prefix(P)
    x, y = P + "x", P + "y"
    eng.create_node(x)
    eng.create_node(y)
    eng.create_edge(x, "R", y)
    store = eng._store

    r = {}
    r["SPJ_in_y_x"] = attempt("ShortestPathJson(y, x, 'in')  truth: 1-hop path", lambda: c.call(TP, "ShortestPathJson", y, x, 5, "", "in"))
    r["SPJ_side_y_x"] = attempt("ShortestPathJson(y, x, 'sideways')", lambda: c.call(TP, "ShortestPathJson", y, x, 5, "", "sideways"))
    r["SL_in_y_x"] = attempt("ShortestLength(y, x, 'in')  truth: 1", lambda: c.call(TP, "ShortestLength", y, x, 5, "", "in"))
    r["SL_in_x_y"] = attempt("ShortestLength(x, y, 'in')  truth: -1 (no path against the edges)", lambda: c.call(TP, "ShortestLength", x, y, 5, "", "in"))
    r["SL_side_x_y"] = attempt("ShortestLength(x, y, 'sideways')", lambda: c.call(TP, "ShortestLength", x, y, 5, "", "sideways"))
    r["DJ_in_y_x"] = attempt("DijkstraJson(y, x, 'in')", lambda: c.call(TP, "DijkstraJson", y, x, "", 9999, 10, "in", "", ""))
    r["DJ_side_y_x"] = attempt("DijkstraJson(y, x, 'sideways')", lambda: c.call(TP, "DijkstraJson", y, x, "", 9999, 10, "sideways", "", ""))
    r["store_path_in_y_x"] = attempt("store.execute_shortest_path(y, x, 'in')", lambda: store.execute_shortest_path(y, x, [], 5, "in", False).rows)
    r["store_path_in_x_y"] = attempt("store.execute_shortest_path(x, y, 'in')  truth: none", lambda: store.execute_shortest_path(x, y, [], 5, "in", False).rows)
    r["store_len_in_x_y"] = attempt("store.shortest_path_length(x, y, 'in')  truth: -1", lambda: store.shortest_path_length(x, y, [], 5, "in"))
    r["store_len_in_y_x"] = attempt("store.shortest_path_length(y, x, 'in')  truth: 1", lambda: store.shortest_path_length(y, x, [], 5, "in"))
    q = f"MATCH p = shortestPath((a {{node_id: '{y}'}})<-[*..5]-(b {{node_id: '{x}'}})) RETURN length(p)"
    r["cypher_in_len"] = attempt("Cypher shortestPath (y)<-[*..5]-(x) length", lambda: eng.execute_cypher(q).rows)

    spj_silent = str(r["SPJ_in_y_x"]).strip() in ("[]", "")
    sl_false_pos = str(r["SL_in_x_y"]).strip() == "1"
    dj_refuses = str(r["DJ_side_y_x"]).startswith("RAISED")
    print("RESULT ShortestPathJson answers 'in' as no path (silent):", spj_silent)
    print("RESULT ShortestLength reads 'in' as 'out' (false positive length 1 where none exists):", sl_false_pos)
    print("RESULT store.shortest_path_length(x, y, 'in') disagrees with execute_shortest_path(x, y, 'in') "
          "(its docstring: 'what execute_shortest_path's paths' length is'):",
          str(r["store_len_in_x_y"]) == "1" and r["store_path_in_x_y"] == [])
    print("RESULT DijkstraJson refuses an unknown direction:", dj_refuses)
    eng.delete_nodes_by_prefix(P)
    c.close()


if __name__ == "__main__":
    main()
