"""W24 native probe: variable-length path multiplicity on a diamond (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W24D_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def main():
    c = runtime.connect()
    from iris_vector_graph.engine import IRISGraphEngine
    e = IRISGraphEngine(c, embedding_dimension=768)  # default: native executor on
    n = {k: f"vld{RUN}{k}" for k in "axyb"}; R = f"VLDR{RUN}"
    for v in n.values(): e.create_node(v, labels=["VL"])
    for s, t in [("a", "x"), ("x", "b"), ("a", "y"), ("y", "b"), ("a", "b")]: e.create_edge(n[s], R, n[t])
    base = f"MATCH (s {{id: '{n['a']}'}})-[:{R}*"
    qs = {"1..2 rows": base + "1..2]->(t) RETURN t.id", "1..2 count": base + "1..2]->(t) RETURN count(*)",
          "1..2 distinct": base + "1..2]->(t) RETURN DISTINCT t.id", "1..2 grouped": base + "1..2]->(t) RETURN t.id, count(*)",
          "2..2 rows": base + "2..2]->(t) RETURN t.id", "0..1 rows": base + "0..1]->(t) RETURN t.id"}
    out = {"run": RUN, "fixture": runtime.NAME, "nodes": n, "queries": {}}
    short = {v: k for k, v in n.items()}
    for k, q in qs.items():
        r = e.execute_cypher(q)
        out["queries"][k] = {"query": q, "rows": [list(x) for x in r["rows"]], "error": str(r.error) if getattr(r, "error", None) else None}
    c.close()
    path = HERE / f"varlength-default-engine-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, x in out["queries"].items():
        print(f"{k:14s}", sorted([[short.get(v, v) for v in row] for row in x["rows"]], key=str), x["error"] or "")
if __name__ == "__main__":
    main()
