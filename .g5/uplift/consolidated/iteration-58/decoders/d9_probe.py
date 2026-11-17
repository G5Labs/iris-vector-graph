import sys, json
sys.path.insert(0, sys.argv[1] + '/.g5/uplift/consolidated/iteration-36'); import runtime
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph.cypher.translator import translate_to_sql
P='i58d_080853_'; K='I58DK080853'
shapes = {
 'rvar': f"MATCH (a {{node_id: '{P}i'}})-[r:{K}*1..3]->(b) RETURN b.node_id AS id",
 'path': f"MATCH p = (a {{node_id: '{P}i'}})-[:{K}*1..3]->(b) RETURN b.node_id AS id",
 'pathlen': f"MATCH p = (a {{node_id: '{P}i'}})-[:{K}*1..3]->(b) RETURN b.node_id AS id, length(p) AS l",
 'opt': f"MATCH (a {{node_id: '{P}i'}}) OPTIONAL MATCH (a)-[:{K}*1..3]->(b) RETURN b.node_id AS id",
 'rlen': f"MATCH (a {{node_id: '{P}i'}})-[r:{K}*1..3]->(b) RETURN b.node_id AS id, size(r) AS l",
}
c = runtime.connect(); e = runtime.engine(c)
out = {}
for k, q in shapes.items():
    try:
        vl = translate_to_sql(parse_query(q), {}).var_length_paths
    except Exception as x:
        vl = repr(x)
    row = {'vlp': bool(vl) if not isinstance(vl, str) else vl}
    for suf, s in (('all', ' ORDER BY id'), ('limit', ' LIMIT 2'), ('order_limit', ' ORDER BY id LIMIT 2'), ('order_desc_limit', ' ORDER BY id DESC LIMIT 2'), ('skip_limit', ' ORDER BY id SKIP 1 LIMIT 2')):
        try:
            r = e.execute_cypher(q + s, {})
            row[suf] = [list(x) for x in r.rows]
        except Exception as x:
            row[suf] = repr(x)[:200]
    out[k] = row
    print(k, json.dumps(row, default=repr))
c.close()
json.dump({'driver': __import__('importlib.metadata').metadata.version('intersystems-irispython'), 'shapes': shapes, 'out': out}, open(sys.argv[2], 'w'), indent=1, default=repr)
