import sys
sys.path.insert(0, sys.argv[1] + '/.g5/uplift/consolidated/iteration-36'); import runtime
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph.cypher.translator import translate_to_sql
c = runtime.connect(); e = runtime.engine(c)
P='i58d_080853_'; K='I58DK080853'
for q in [f"MATCH (a {{node_id: '{P}i'}})-[:{K}*1..3]->(b) RETURN b.node_id AS id LIMIT 2",
          f"MATCH (a {{node_id: '{P}i'}})-[r:{K}*1..3]->(b) RETURN b.node_id AS id, r LIMIT 2",
          f"MATCH p = shortestPath((a {{node_id: '{P}i'}})-[:{K}*1..3]->(b {{node_id: '{P}b'}})) RETURN length(p) AS l LIMIT 2",
          f"MATCH (a {{node_id: '{P}i'}}) OPTIONAL MATCH (a)-[r:{K}*1..3]->(b) RETURN b.node_id AS id, size(r) AS n LIMIT 2"]:
    try:
        sq = translate_to_sql(parse_query(q), {}, engine=e); vl = bool(sq.var_length_paths)
    except Exception as x:
        vl = repr(x)[:100]
    called = []
    orig = e._route_var_length
    e._route_var_length = lambda *a, **k: (called.append(1), orig(*a, **k))[1]
    try:
        r = e.execute_cypher(q, {}); rows = [list(x) for x in r.rows]
        r2 = e.execute_cypher(q.replace(" LIMIT 2", ""), {}); n_all = len(r2.rows)
    except Exception as x:
        rows = repr(x)[:200]; n_all = None
    e._route_var_length = orig
    print(vl, len(called), n_all, rows)
c.close()
