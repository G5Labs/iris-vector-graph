"""node_edge_update binding: the W39 cases with fresh IDs through the actual store_node, delete_node, set_edge_weight
and delete_edge, read back by get_node, Cypher and ^KG on the run-isolated retest fixture, compared with a port of
node_edge_update.rs; six port mutations mirror the controls. Ordinary data, fixture only."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("NE_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
MUTS = ["none_keeps_property", "labels_replaced", "delete_node_keeps_edges", "weight_any_graph", "delete_edge_every_graph", "new_node_no_id"]
def predict(m):
    return {"U1": {"p": 2, "q": None if not m.get("none_keeps_property") else "x", "labels": ["NB"] if m.get("labels_replaced") else ["NA", "NB"], "ret": True},
            "U2": {"p": 3, "id_prop": not m.get("new_node_no_id")},
            "D1": {"node": False, "edge": False if not m.get("delete_node_keeps_edges") else True, "kg": False if not m.get("delete_node_keeps_edges") else True, "k": True},
            "W1": {"ret": True, "cypher": 2.5, "kg": 2.5}, "W2": {"ret": True if m.get("weight_any_graph") else False, "count": 1 if m.get("weight_any_graph") else 0},
            "W3": {"ret": True if m.get("weight_any_graph") else False, "named": 1.0},
            "E1": {"ret": True, "count": 0, "kg": False}, "E2": {"ret": True}, "E3": {"ret": True, "named": 0 if m.get("delete_edge_every_graph") else 1}}
def main():
    import iris
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c)
    def rows(q, p=None):
        r = e.execute_cypher(q, p or {}); return [list(x) for x in (r.rows if hasattr(r, "rows") else r["rows"])]
    n, m_, k, s, o, g = f"ne{TAG}n", f"ne{TAG}m", f"ne{TAG}k", f"ne{TAG}s", f"ne{TAG}o", f"neg{TAG}"
    got = {}
    e.create_node(n, labels=["NA"], properties={"p": 1, "q": "x"}); r = e.store_node(n, {"p": 2, "q": None}, labels=["NB"])
    x = e.get_node(n); got["U1"] = {"p": x.get("p"), "q": x.get("q"), "labels": sorted(x["labels"]), "ret": r}
    e.store_node(m_, {"p": 3}); x = e.get_node(m_); got["U2"] = {"p": x.get("p"), "id_prop": x.get("p_id") == m_}
    e.create_node(k); e.create_edge(n, "NER", k); e.delete_node(n)
    got["D1"] = {"node": e.get_node(n) is not None, "edge": bool(rows("MATCH (a)-[r:NER]->(b {id: $k}) RETURN a.id", {"k": k})),
                 "kg": bool(nat.isDefined("^KG", "out", 0, n, "NER", k)), "k": e.get_node(k) is not None}
    e.create_node(s); e.create_node(o); e.create_edge(s, "NEW", o, weight=1.0); r = e.set_edge_weight(s, "NEW", o, 2.5)
    got["W1"] = {"ret": r, "cypher": rows("MATCH (a {id: $s})-[r:NEW]->(b) RETURN r.weight", {"s": s})[0][0], "kg": float(nat.get("^KG", "out", 0, s, "NEW", o))}
    r = e.set_edge_weight(s, "NENONE", o, 3.0); got["W2"] = {"ret": r, "count": rows("MATCH (a {id: $s})-[r:NENONE]->(b) RETURN count(r)", {"s": s})[0][0]}
    e.create_node(s + "g", graph=g); e.create_node(o + "g", graph=g); e.create_edge(s + "g", "NEG", o + "g", weight=1.0, graph=g)
    r = e.set_edge_weight(s + "g", "NEG", o + "g", 9.0); got["W3"] = {"ret": r, "named": rows(f"USE GRAPH '{g}' MATCH (a {{id: '{s}g'}})-[r:NEG]->(b) RETURN r.weight")[0][0]}
    r = e.delete_edge(s, "NEW", o); got["E1"] = {"ret": r, "count": rows("MATCH (a {id: $s})-[r:NEW]->(b) RETURN count(r)", {"s": s})[0][0], "kg": bool(nat.isDefined("^KG", "out", 0, s, "NEW", o))}
    got["E2"] = {"ret": e.delete_edge(s, "NENONE", o)}
    r = e.delete_edge(s + "g", "NEG", o + "g"); got["E3"] = {"ret": r, "named": rows(f"USE GRAPH '{g}' MATCH (a {{id: '{s}g'}})-[r:NEG]->(b) RETURN count(r)")[0][0]}
    c.close()
    want = predict({}); mism = [{"case": kk, "observed": got[kk], "expected": want[kk]} for kk in want if got[kk] != want[kk]]
    sens = {mm: sum(1 for kk, v in predict({mm: True}).items() if v != got[kk]) for mm in MUTS}
    body = {"kind": "binding", "model": "node_edge_update", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT, "run": RUN,
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "comparisons": sum(len(v) for v in want.values()), "mismatches": mism,
            "observed": got, "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "node_edge_update.rs", HERE / "model.json"]},
                       "iris_vector_graph/_engine/nodes_edges.py": sha(Path(runtime.PIN) / "iris_vector_graph/_engine/nodes_edges.py")},
            "scope": "Actual store_node, delete_node, set_edge_weight, delete_edge on IRIS 2026.1 (pin 3eaa79cf); one history per case, read back "
                     "through get_node, Cypher and ^KG. delete_node's documents, vectors and reifier cleanup and delete_edge(all_graphs=True) are not exercised."}
    d = REPO / ".g5/Verus_verification/results/node_edge_update" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({kk: body[kk] for kk in ("verdict", "cases", "comparisons", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism: print("MISMATCH", json.dumps(x, default=str))
if __name__ == "__main__":
    main()
