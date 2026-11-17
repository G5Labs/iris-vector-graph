import json, os, sys, time
REPO = os.environ["IVG_REPO"]
sys.path.insert(0, REPO + "/.g5/Verus_verification/tools"); sys.path.insert(0, REPO + "/.g5/uplift/consolidated/iteration-36")
import binding_common as bc
bc.import_pin()
import runtime
from iris_vector_graph.engine import IRISGraphEngine
TAG = time.strftime("%H%M%S", time.gmtime()); P = f"rv58w_{TAG}_"
c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768, native_cypher=False)
L = f"RV58W{TAG}"
e.create_node(P + "n1", labels=[L], properties={"f": 2.0, "g": -3.0, "h": 2.5, "i": 2})
out = {}
for k, q in {"ret": f"MATCH (n:{L}) RETURN n.f AS f, n.g AS g, n.h AS h, n.i AS i",
             "with": f"MATCH (n:{L}) WITH n.f AS f, n.i AS i RETURN f, i",
             "coalesce": f"MATCH (n:{L}) RETURN coalesce(n.f, 0) AS f"}.items():
    r = e.execute_cypher(q); out[k] = [[(v, type(v).__name__) for v in row] for row in r.rows] if r.rows else r.error
out["get_node"] = {k: (v, type(v).__name__) for k, v in (e.get_node(P + "n1") or {}).get("properties", {}).items()} if isinstance(e.get_node(P + "n1"), dict) else str(e.get_node(P + "n1"))[:300]
cur = c.cursor(); cur.execute(f"SELECT key, val FROM {e._schema_prefix}.rdf_props WHERE s = ?", [P + "n1"]); out["stored"] = [list(map(repr, r)) for r in cur.fetchall()]
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(f"/tmp/review-56-58/probes/probe3-{TAG}.json", "w"), indent=1, default=str)
