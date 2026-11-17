import sys, json, time
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/iris-uplift-master-workers-20261117/iris-vector-graph/.g5/uplift/consolidated/iteration-36")
import runtime
TAG = time.strftime("%H%M%S", time.gmtime()); P = f"i58c_{TAG}_"; L = f"I58C{TAG}"
c = runtime.connect(); e = runtime.engine(c)
from importlib.metadata import version; print("driver", version("intersystems-irispython"))
def run(q):
    try:
        r = e.execute_cypher(q, {}); print(json.dumps({"q": q, "rows": [list(x) for x in r.rows], "cols": list(getattr(r, "columns", []) or [])}, default=repr))
    except Exception as x:
        print(json.dumps({"q": q, "err": f"{type(x).__name__}: {str(x)[:160]}"}))
K = f"K{TAG}"
e.create_node(P+"a1", labels=[L+"A"], properties={"name": "a1", "v": 1}); e.create_node(P+"b1", labels=[L+"B"], properties={"name": "b1", "v": 10})
e.create_edge(P+"a1", K, P+"b1")
run(f"OPTIONAL MATCH (b:{L}NONE) RETURN count(b), count(*), sum(b.v), collect(b.v), avg(b.v), min(b.v)")
run(f"OPTIONAL MATCH (b:{L}NONE) RETURN sum(b.v)")
run(f"OPTIONAL MATCH (b:{L}NONE) RETURN b, sum(b.v), count(*)")
run(f"OPTIONAL MATCH (b:{L}NONE) RETURN b.v AS k, sum(b.v), count(b)")
run(f"MATCH (a:{L}A)-[:{K}]->(b) WITH * RETURN a.name, b.name")
run(f"MATCH (a:{L}A)-[r:{K}]->(b) WITH a, r, b RETURN a.name, type(r), b.name")
run(f"MATCH (a:{L}A)-[r:{K}]->(b) WITH * RETURN a.name")
run("WITH [1, true] AS l UNWIND l AS x RETURN x, count(*)")
run("WITH [1, true] AS l UNWIND l AS x RETURN DISTINCT x")
run(f"MATCH (n {{id: '{P}a1'}}) FOREACH (x IN [1,2] | SET n.f = 5)")
print("GET", json.dumps(e.get_node(P+"a1"), default=repr))
run(f"MATCH (a:{L}A) CALL {{ WITH a MATCH (a)-[:{K}]->(b) RETURN count(b) AS c }} RETURN a.name, c")
c.close()
