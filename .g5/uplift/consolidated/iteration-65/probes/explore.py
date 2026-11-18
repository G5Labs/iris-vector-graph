import json, sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime, obs
NS = "I65X"
obs.recreate(NS)
c = runtime.connect(NS)
e = runtime.engine(c, namespace=NS)
e.initialize_schema()
cur = c.cursor()
def q(sql, p=()):
    cur.execute(sql, list(p)); 
    try: return cur.fetchall()
    except Exception: return None
def step(name, f):
    try:
        r = f(); print("OK", name, repr(r)[:200])
    except Exception as x:
        print("ERR", name, type(x).__name__, str(x)[:300])
step("node g1 a", lambda: e.create_node("a", ["P"], {"name": "alpha"}, graph="g1"))
step("node g1 b", lambda: e.create_node("b", ["P"], {"name": "beta"}, graph="g1"))
step("node g2 a", lambda: e.create_node("a", ["P"], {"name": "alpha2"}, graph="g2"))
step("node g2 b", lambda: e.create_node("b", ["P"], {"name": "beta2"}, graph="g2"))
step("node def a", lambda: e.create_node("a", ["P"], {"name": "alpha0"}))
step("edge g1", lambda: e.create_edge("a", "R", "b", graph="g1"))
step("edge g2", lambda: e.create_edge("a", "R", "b", graph="g2"))
step("edge def", lambda: e.create_edge("a", "R", "c"))
step("bulk edges def", lambda: e.bulk_create_edges([{"source_id": "x", "predicate": "R", "target_id": "y"}]) if hasattr(e, "bulk_create_edges") else None)
step("bulk nodes def", lambda: e.bulk_create_nodes([{"id": "x", "labels": ["P"]}, {"id": "y"}]))
step("temporal g1", lambda: e.create_edge_temporal("a", "T", "b", timestamp=1700000000, graph="g1"))
step("temporal-only set", lambda: e.set_temporal_structural("g1", "EV", False) if True else None)
step("temporal-only ev", lambda: e.create_edge_temporal("t1", "EV", "t2", timestamp=1700000100, graph="g1"))
step("multigraph g1", lambda: e.set_multigraph("g1", True))
step("emb g1", lambda: e.store_embedding("a", [0.1]*768, graph="g1"))
step("emb def", lambda: e.store_embedding("a", [0.2]*768))
step("edge id g1", lambda: q("SELECT edge_id FROM Graph_KG.rdf_edges WHERE graph_id='g1'"))
eid = q("SELECT edge_id FROM Graph_KG.rdf_edges WHERE graph_id='g1'")[0][0]
step("reify g1", lambda: e.reify_edge(eid, props={"why": "secret"}))
step("bm25 g1", lambda: e.bm25_build("ix1", ["name"], graph="g1"))
step("bm25 search", lambda: e.bm25_search("ix1", "alpha", 5) if hasattr(e, "bm25_search") else None)
from iris_vector_graph.ledger import Changeset
def led():
    e.ledger.enable()
    cs = Changeset(actor="t", actor_type="system", auto_stub_missing_nodes=True)
    cs.create_relationship("l1", "R", "l2", graph="g1")
    cs.create_relationship("l1", "R", "l2", graph="g2")
    return e.ledger.commit(cs)
step("ledger", led)
for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props", "kg_NodeEmbeddings", "embedding_registry", "rdf_reifications", "docs", "embedding_quarantine", "fhir_graphs", "fhir_unresolved"):
    step("count " + t, lambda t=t: q(f"SELECT CASE WHEN graph_id IS NULL THEN 'NULL' ELSE graph_id END, COUNT(*) FROM Graph_KG.{t} GROUP BY graph_id") if t not in ("rdf_reifications",) else q(f"SELECT COUNT(*) FROM Graph_KG.{t}"))
step("registry", lambda: q("SELECT graph_id, table_name, model_key, kind FROM Graph_KG.embedding_registry"))
step("routed tables", lambda: q("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='Graph_KG' AND TABLE_NAME %STARTSWITH 'kg_emb_'"))
step("tables", lambda: [r[0] for r in q("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='Graph_KG'")])
print(json.dumps(obs.globals_counts(NS, ["g1", "g2", 0]), indent=0)[:3000])
