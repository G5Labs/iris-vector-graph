import sys,os
sys.path.insert(0,os.environ['IVG_PIN_DIR'])
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph.cypher.translator import translate_to_sql
qs=["USE GRAPH 'g' MATCH (n:Report) RETURN count(*) AS allrows,count(n.v) AS nonnull,count(DISTINCT n.v) AS uniq", "USE GRAPH 'g' MATCH (n:Report) RETURN n.k AS k,count(*) AS c,sum(n.v) AS total,avg(n.v) AS mean", "USE GRAPH 'g' MATCH (n:Report) WITH sum(n.v) AS s RETURN s", "UNWIND [1, null, 1, 2.5] AS x RETURN collect(x) AS xs,collect(DISTINCT x) AS dx", "UNWIND [false,true,null] AS x RETURN collect(x) AS xs", "USE GRAPH 'g' MATCH (n:Report) RETURN n.k AS k,count(*) AS c ORDER BY c DESC SKIP 1 LIMIT 1", "MATCH (n:Report) RETURN count(DISTINCT n) AS c"]
from types import SimpleNamespace
for q in qs:
 s=translate_to_sql(parse_query(q),{},engine=SimpleNamespace(_fetch_first_unsafe=True,get_table_mapping=lambda *a,**k:None,get_rel_mapping=lambda *a,**k:None))
 print(q);print(s.sql);print({k:v for k,v in vars(s).items() if v and k!='sql'})
