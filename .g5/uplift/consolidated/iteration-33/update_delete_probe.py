"""W39: store_node / delete_node / set_edge_weight / delete_edge through get_node, Cypher and ^KG (fixture only)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W39_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def main():
    import iris
    c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c); out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    def rows(q, p=None):
        r = e.execute_cypher(q, p or {}); return [list(x) for x in (r.rows if hasattr(r, "rows") else r["rows"])]
    def node(n, g=None):
        x = e.get_node(n, graph=g) if g is not None else e.get_node(n)
        return None if x is None else {k: (sorted(v) if k == "labels" else v) for k, v in x.items()}
    def case(k, fn):
        try: out["cases"][k] = fn()
        except Exception: out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:300]
    n, m, k = f"ud{TAG}n", f"ud{TAG}m", f"ud{TAG}k"
    def u1():
        e.create_node(n, labels=["UA"], properties={"p": 1, "q": "x"})
        r = e.store_node(n, {"p": 2, "q": None}, labels=["UB"])
        return {"returned": r, "get_node": node(n), "cypher": rows("MATCH (x {id: $n}) RETURN x.p, x.q, labels(x)", {"n": n})}
    case("U1_store_existing", u1)
    case("U2_store_new", lambda: {"returned": e.store_node(m, {"p": 3}), "get_node": node(m), "cypher": rows("MATCH (x {id: $n}) RETURN x.p, x.id", {"n": m})})
    def d1():
        e.create_node(k); e.create_edge(n, "UDR", k)
        before = {"edge": rows("MATCH (a {id: $n})-[r:UDR]->(b) RETURN b.id", {"n": n}), "kg": bool(nat.isDefined("^KG", "out", 0, n, "UDR", k))}
        r = e.delete_node(n)
        return {"before": before, "returned": r, "get_node": node(n), "edge_from_k": rows("MATCH (a)-[r:UDR]->(b {id: $k}) RETURN a.id", {"k": k}),
                "kg_out": bool(nat.isDefined("^KG", "out", 0, n, "UDR", k)), "kg_in": bool(nat.isDefined("^KG", "in", 0, k, "UDR", n)), "k_stays": node(k) is not None}
    case("D1_delete_node", d1)
    s, o = f"ud{TAG}s", f"ud{TAG}o"
    def w1():
        e.create_node(s); e.create_node(o); e.create_edge(s, "UDW", o, weight=1.0)
        r = e.set_edge_weight(s, "UDW", o, 2.5)
        cy = rows("MATCH (a {id: $s})-[r:UDW]->(b) RETURN r.weight, properties(r)", {"s": s})
        return {"returned": r, "cypher": cy, "cypher_types": [[type(v).__name__ for v in row] for row in cy], "kg": nat.get("^KG", "out", 0, s, "UDW", o)}
    case("W1_set_weight", w1)
    case("W2_set_weight_missing", lambda: {"returned": e.set_edge_weight(s, "UDNONE", o, 3.0), "cypher": rows("MATCH (a {id: $s})-[r:UDNONE]->(b) RETURN count(r)", {"s": s})})
    g = f"udg{TAG}"
    def w3():
        e.create_node(f"{s}g", graph=g); e.create_node(f"{o}g", graph=g); e.create_edge(f"{s}g", "UDG", f"{o}g", weight=1.0, graph=g)
        r = e.set_edge_weight(f"{s}g", "UDG", f"{o}g", 9.0)
        return {"returned": r, "named_graph_weight": rows(f"USE GRAPH '{g}' MATCH (a {{id: '{s}g'}})-[r:UDG]->(b) RETURN r.weight")}
    case("W3_set_weight_named_graph", w3)
    def e1():
        r = e.delete_edge(s, "UDW", o)
        return {"returned": r, "cypher": rows("MATCH (a {id: $s})-[r:UDW]->(b) RETURN count(r)", {"s": s}), "kg": bool(nat.isDefined("^KG", "out", 0, s, "UDW", o))}
    case("E1_delete_edge", e1)
    case("E2_delete_missing", lambda: {"returned": e.delete_edge(s, "UDNONE", o)})
    def e3():
        r = e.delete_edge(f"{s}g", "UDG", f"{o}g")
        return {"returned": r, "named_graph_edge": rows(f"USE GRAPH '{g}' MATCH (a {{id: '{s}g'}})-[r:UDG]->(b) RETURN count(r)")}
    case("E3_delete_named_without_graph", e3)
    c.close(); path = HERE / f"update-delete-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for kk, v in out["cases"].items(): print("==", kk, json.dumps(v, default=str)[:500])
if __name__ == "__main__":
    main()
