import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime, obs
NS = "I65Z"
obs.recreate(NS)
c = runtime.connect(NS)
e = runtime.engine(c, namespace=NS)
e.initialize_schema()
cur = c.cursor()
def q(sql, p=()):
    cur.execute(sql, list(p))
    try: return cur.fetchall()
    except Exception: return None
def step(name, f):
    try:
        r = f(); print("OK", name, repr(r)[:300]); return r
    except Exception as x:
        print("ERR", name, type(x).__name__, str(x)[:400]); return x
step("nodes", lambda: e.bulk_create_nodes([{"id": f"n{i:04d}", "labels": ["P"]} for i in range(6)], graph="g1") if "graph" in e.bulk_create_nodes.__code__.co_varnames else e.bulk_create_nodes([{"id": f"n{i:04d}", "labels": ["P"]} for i in range(6)]))
for i in range(6):
    step(f"node g2 n{i}", lambda i=i: e.create_node(f"n{i:04d}", ["P"], {}, graph="g2"))
step("edges", lambda: [e.create_edge("n0000", "R", "n0001", graph="g2"), e.create_edge("n0001", "R", "n0002", graph="g2")])
step("pagerank g2", lambda: e.pagerank(graph="g2") if "graph" in str(e.pagerank.__doc__) else e.pagerank())
print(json.dumps({k: v for k, v in obs.globals_counts(NS, ["g2", 0]).items() if "AlgoCache" in k}))
long_id = "L" * 700
step("store.delete_nodes long only", lambda: e._store.delete_nodes([long_id], graph="g2"))
step("store.delete_nodes [n0003, long]", lambda: e._store.delete_nodes(["n0003", long_id], graph="g2"))
step("count g2 n0003", lambda: q("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id='g2' AND node_id='n0003'"))
step("delete_node long", lambda: e.delete_node(long_id, graph="g2"))
step("erase_graph long name", lambda: e.erase_graph("G" * 300))
# from_connect + caller transaction
from iris_vector_graph.engine import IRISGraphEngine
e2 = step("from_connect", lambda: IRISGraphEngine.from_connect("127.0.0.1", runtime.PORT, NS, "_SYSTEM", "SYS", embedding_dimension=768))
if not isinstance(e2, Exception):
    c2 = e2.conn
    c2.setAutoCommit(False)
    step("caller write g9", lambda: e2.create_node("z", ["P"], {}, graph="g9"))
    step("erase g2 on from_connect", lambda: e2.erase_graph("g2"))
    c2.rollback()
    c2.setAutoCommit(True)
    step("g2 nodes after caller rollback", lambda: q("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id='g2'"))
    step("g9 nodes after caller rollback", lambda: q("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id='g9'"))
