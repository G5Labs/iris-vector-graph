import sys, json, time, os
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/iris-uplift-master-workers-20261117/iris-vector-graph/.g5/uplift/consolidated/iteration-36")
import runtime
import iris
TAG = time.strftime("%H%M%S", time.gmtime())
P = f"i58c_{TAG}_"; L = f"I58C{TAG}"
c = runtime.connect(); e = runtime.engine(c)
print("driver", getattr(iris, "__version__", None))
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph.cypher import translator as T
def run(q, params=None, sql=False):
    out = {}
    try:
        r = e.execute_cypher(q, params or {})
        out["rows"] = [list(x) for x in r.rows] if not getattr(r, "error", None) else None
        if getattr(r, "error", None): out["err"] = str(r.error)[:200]
    except Exception as x:
        out["err"] = f"{type(x).__name__}: {str(x)[:200]}"
    if sql:
        try:
            s = T.translate_to_sql(parse_query(q), params or {})
            out["sql"] = str(getattr(s, "sql", s))[:1500]
        except Exception as x:
            out["sqlerr"] = repr(x)[:200]
    print(json.dumps({"q": q, **out}, default=repr)); sys.stdout.flush()
    return out
K = f"K{TAG}"
# C1 data
for n, v in (("a1", 1), ("a2", 2), ("b1", 10), ("b2", 20)):
    e.create_node(P + n, labels=[L + ("A" if n[0] == "a" else "B")], properties={"v": v, "name": n})
e.create_edge(P + "a1", K, P + "b1"); e.create_edge(P + "a1", K, P + "b2")
A = L + "A"
run(f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:NONE{TAG}]->(b) RETURN a.name, count(b), count(*) ORDER BY a.name", sql=True)
run(f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, count(b), count(*) ORDER BY a.name", sql=True)
run(f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, collect(b.name), sum(b.v), avg(b.v) ORDER BY a.name", sql=True)
run(f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, min(b.v), max(b.v), count(DISTINCT b), collect(b) ORDER BY a.name")
run(f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN count(b), count(*)")
# C2
for lst in ("[1,'1']", "[1,true]", "[1,1.0]", "['true',true]", "[[1],'[1]']"):
    run(f"UNWIND {lst} AS x RETURN x, count(*) ORDER BY count(*)", sql=True)
    run(f"UNWIND {lst} AS x RETURN DISTINCT x")
    run(f"UNWIND {lst} AS x RETURN count(DISTINCT x)")
# C3
for cond in ("b.v = a.v + 1", "b.v = 10 OR b.v = 30", "b.v - 1 = 9", "b.v + 0 = 10", "b.v * 2 = 40", "b.v = 10 OR b.name = 'zz'", "b.v = a.v OR b.v = 10", "NOT b.v = 10", "b.v IN [10, 30]"):
    run(f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE {cond} RETURN a.name, b.name ORDER BY a.name, b.name", sql=(cond in ("b.v = 10 OR b.v = 30", "b.v - 1 = 9")))
# C9
LM = L + "M"
for i, v in enumerate(("a", True, 2, 1.5, None)):
    e.create_node(f"{P}m{i}", labels=[LM], properties=({"v": v} if v is not None else {"w": 0}))
run(f"MATCH (n:{LM}) WITH n.v AS v ORDER BY v RETURN v", sql=True)
run(f"MATCH (n:{LM}) WITH n.v AS v ORDER BY v DESC RETURN v")
run(f"MATCH (n:{LM}) RETURN n.v AS v ORDER BY v")
run(f"MATCH (n:{LM}) RETURN n.v AS v ORDER BY v DESC")
# C4
LU = L + "U"
e.create_node(P + "u1", labels=[LU], properties={"f": 2.5, "l": [1, 2], "i": 3})
run(f"MATCH (n:{LU}) RETURN n.f AS x UNION RETURN 2.5 AS x", sql=True)
run(f"MATCH (n:{LU}) RETURN n.f AS x UNION ALL RETURN 1 AS x")
run(f"MATCH (n:{LU}) RETURN n.l AS x UNION ALL RETURN 1 AS x")
run(f"MATCH (n:{LU}) RETURN n.l AS x")
run(f"MATCH ()-[r:{K}]->() RETURN r AS x UNION ALL MATCH ()-[r:{K}]->() RETURN r AS x")
run(f"MATCH ()-[r:{K}]->() RETURN r AS x")
# C5
run(f"MATCH (a:{A}) CALL {{ WITH a MATCH (a)-[:{K}]->(b) RETURN count(b) AS c }} RETURN a.name, c ORDER BY a.name", sql=True)
run(f"MATCH (a:{A}) CALL {{ WITH a MATCH (a)-[:{K}]->(b) RETURN b.name AS c }} RETURN a.name, c ORDER BY a.name, c")
# C7
for nm in ("s1", "s2", "s3"):
    e.create_node(P + nm, labels=[L + "S"], properties={"a": "old", "c": "keep"})
run(f"MATCH (n {{id: '{P}s1'}}) SET n += {{a: 1, b: null}} RETURN n.a, n.b, n.c", sql=True)
print("GET s1", json.dumps(e.get_node(P + "s1"), default=repr))
run(f"MATCH (n {{id: '{P}s2'}}) SET n = {{a: 1}} RETURN n.a, n.c")
print("GET s2", json.dumps(e.get_node(P + "s2"), default=repr))
run(f"MATCH (n {{id: '{P}s3'}}) SET n += {{t: toUpper('x')}} RETURN n.t")
print("GET s3", json.dumps(e.get_node(P + "s3"), default=repr))
# C8
run(f"MATCH (a:{A})-[r:{K}]->(b) WITH * RETURN a.name, type(r), b.name ORDER BY b.name", sql=True)
run(f"MATCH (a:{A})-[r:{K}]->(b) RETURN a.name, type(r), b.name ORDER BY b.name")
run(f"MATCH (a:{A}) WITH *, a.v AS av RETURN av ORDER BY av")
# C6
LF = L + "F"
e.create_node(P + "f1", labels=[LF], properties={"f": 0})
run(f"MATCH (n {{id: '{P}f1'}}) FOREACH (x IN [1,2] | SET n.f = x)")
print("GET f1", json.dumps(e.get_node(P + "f1"), default=repr))
run(f"MATCH (n {{id: '{P}f1'}}) FOREACH (x IN [1,2] | CREATE (:{L}FM {{v:x}}))")
run(f"MATCH (m:{L}FM) RETURN m.v ORDER BY m.v")
run(f"MATCH (n {{id: '{P}f1'}}) FOREACH (x IN [] | SET n.f = 99)")
print("GET f1b", json.dumps(e.get_node(P + "f1"), default=repr))
c.close()
