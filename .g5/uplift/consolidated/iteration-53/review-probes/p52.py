import sys, json; sys.path.insert(0,'/tmp/review-50-52/probe'); import rt
c=rt.connect(); e=rt.eng(c); cur=c.cursor(); out={}
reg=e._registry_table(); out["registry"]=reg
cur.execute(f"SELECT table_name, COALESCE(kind,'node') FROM {reg}"); plain=cur.fetchall(); out["plain_rows"]=[list(r) for r in plain][:10]
cur.execute(f"SELECT DISTINCT table_name, COALESCE(kind,'node') FROM {reg}"); dist=cur.fetchall(); out["distinct_rows"]=[list(r) for r in dist][:10]
from iris_vector_graph.security import is_routed_embedding_table as isr
out["is_route_plain"]=[isr(str(r[0])) for r in plain][:10]; out["is_route_distinct"]=[isr(str(r[0])) for r in dist][:10]
errs=[]; out["embedding_tables"]=e._embedding_tables(cur,"node",errs)
routed=0
for r in plain:
    if str(r[1])=="node" and isr(str(r[0])):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {e._t(str(r[0]))}"); routed+=int(cur.fetchone()[0])
        except Exception as x: out.setdefault("count_err",[]).append(str(x)[:100])
cur.execute(f"SELECT COUNT(*) FROM {e._t(e._legacy_table_for('node'))}"); legacy=int(cur.fetchone()[0])
s=e.status(); out.update(routed_rows=routed, legacy_rows=legacy, status_node_embeddings=s.tables.node_embeddings, ready_for_vector_search=s.ready_for_vector_search, vector_index_state=s.vector_index_state, status_errors=s.errors[:5], unknown=s.unknown)
vs=e.verify_sync(heal=False); out["verify_sync"]=vs.to_dict()
print(json.dumps(out, indent=1, default=str))
json.dump(out, open("/tmp/review-50-52/probe/p52-out.json","w"), indent=1, default=str)
