import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime, obs
from iris_vector_graph.engine import IRISGraphEngine
NS = "I65Z"
obs.recreate(NS)
c = runtime.connect(NS)
e = IRISGraphEngine(c, embedding_dimension=8, namespace=NS)
e.initialize_schema()
cur = c.cursor()
def q(sql):
    cur.execute(sql); return cur.fetchall()
e.create_node("a", ["P"], {}, graph="g1")
for variant in ("store.delete_nodes long", "store.delete_nodes ok", "delete_node long", "erase_graph ok"):
    c.setAutoCommit(False)
    e.create_node("z", ["P"], {}, graph="g9")
    print(variant, "tlevel after caller write", q("SELECT $TLEVEL")[0][0])
    try:
        if variant == "store.delete_nodes long":
            e._store.delete_nodes(["a", "L" * 700], graph="g1")
        elif variant == "store.delete_nodes ok":
            e._store.delete_nodes(["nobody"], graph="g1")
        elif variant == "delete_node long":
            e.delete_node("L" * 700, graph="g1")
        else:
            e.erase_graph("g7")
        print("  no error")
    except Exception as x:
        print("  error", type(x).__name__, str(x)[:150])
    print("  tlevel after call", q("SELECT $TLEVEL")[0][0], "z visible on caller conn", q("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id='g9'")[0][0])
    c.commit(); c.setAutoCommit(True)
    print("  after commit z", q("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id='g9'")[0][0], "a", q("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id='g1'")[0][0])
    e.erase_graph("g9")
