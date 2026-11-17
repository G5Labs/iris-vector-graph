import sys, json, time
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/iris-uplift-master-workers-20261117/iris-vector-graph/.g5/uplift/consolidated/iteration-36")
import runtime
TAG = time.strftime("%H%M%S", time.gmtime()); P = f"i58c_{TAG}_"; L = f"I58C{TAG}"; K = f"K{TAG}"
c = runtime.connect(); e = runtime.engine(c)
e.create_node(P+"a1", labels=[L+"A"], properties={"name": "a1", "v": 1}); e.create_node(P+"a2", labels=[L+"A"], properties={"name": "a2", "v": 2})
e.create_node(P+"b1", labels=[L+"B"], properties={"name": "b1", "v": 10}); e.create_edge(P+"a1", K, P+"b1")
for w in ("NOT (b.v = a.v + 1)", "NOT (NOT ((b.v = a.v) OR (b.v = 10)))", "((b.v = a.v) OR (b.v = 10)) AND (b.v = 10)",
          "NOT ((b.v = 10) AND (b.v = a.v))", "NOT ((b.v + 1 = 11) OR (b.v = a.v))", "(b.v = 10) OR (a.v = 1)", "NOT ((b.v = 10) OR (a.v = 1))"):
    try:
        r = e.execute_cypher(f"MATCH (a:{L}A) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE {w} RETURN a.name, b.name", {})
        print(json.dumps({"w": w, "rows": [list(x) for x in r.rows], "error": str(getattr(r, "error", None))[:80]}))
    except Exception as x:
        print(json.dumps({"w": w, "err": str(x)[:90]}))
c.close()
