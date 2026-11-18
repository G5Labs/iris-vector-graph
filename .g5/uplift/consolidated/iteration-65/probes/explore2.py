import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime, obs
NS = "I65Y"
obs.recreate(NS)
c = runtime.connect(NS)
e = runtime.engine(c, namespace=NS)
e.initialize_schema()
cur = c.cursor()
def q(sql, p=()):
    cur.execute(sql, list(p))
    try: return cur.fetchall()
    except Exception: return None
def tl(): return q("SELECT $TLEVEL")[0][0]
def counts():
    out = {}
    for t in ("nodes", "rdf_edges", "rdf_props", "embedding_registry"):
        out[t] = q(f"SELECT CASE WHEN graph_id IS NULL THEN 'NULL' WHEN graph_id = '' THEN 'EMPTY' ELSE graph_id END AS g, COUNT(*) FROM Graph_KG.{t} GROUP BY CASE WHEN graph_id IS NULL THEN 'NULL' WHEN graph_id = '' THEN 'EMPTY' ELSE graph_id END")
    out["routes"] = q("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='Graph_KG' AND TABLE_NAME %STARTSWITH 'kg_emb_'")
    return out
# default graph spellings
e.create_node("d1", ["P"], {"k": "v"})
q("INSERT INTO Graph_KG.nodes (node_id) VALUES ('dn')")
q("INSERT INTO Graph_KG.rdf_props (s, \"key\", val) VALUES ('dn', 'k', 'v')")
q("INSERT INTO Graph_KG.rdf_edges (s, p, o_id) VALUES ('dn', 'R', 'd1')")
print("default before", counts())
print("erase '' ->", e.erase_graph(""))
print("default after", counts())
# routes inside a caller transaction
e.create_node("a", ["P"], {}, graph="g1")
e.store_embedding("a", [0.1]*768, graph="g1")
print("g1 before", counts())
c.setAutoCommit(False)
e.create_node("z", ["P"], {}, graph="g9")
print("tlevel after caller write", tl())
r = e.erase_graph("g1")
print("erase g1 inside caller txn ->", r, "tlevel", tl())
print("inside", counts())
c.rollback()
print("tlevel after rollback", tl())
print("after caller rollback", counts())
try:
    print("knn g1 after rollback", e.kg_KNN_VEC([0.1]*768, 3, graph="g1") if hasattr(e, "kg_KNN_VEC") else None)
except Exception as x:
    print("knn error", type(x).__name__, str(x)[:300])
try:
    print("store_embedding again", e.store_embedding("a", [0.3]*768, graph="g1"))
except Exception as x:
    print("store error", type(x).__name__, str(x)[:300])
c.setAutoCommit(True)
print("final", counts())
