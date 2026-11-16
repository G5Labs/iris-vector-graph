"""Ordinary source-path residual probes, recorded before deciding any expanded claim."""
import json
from binding import execute,parse_query,translate_to_sql,Caller,pr
qs=[
 "MATCH (n:Report) RETURN n.k AS k,count(DISTINCT n) AS c",
 "USE GRAPH 'g' MATCH (n:Report) RETURN count(*) AS star,count(n.v) AS c,sum(n.v) AS s,avg(n.v) AS a",
 "USE GRAPH 'g' OPTIONAL MATCH (n:Report) RETURN count(*) AS star,count(n.v) AS c,sum(n.v) AS s,avg(n.v) AS a",
 "USE GRAPH 'g' OPTIONAL MATCH (n:Report) RETURN n.k AS k,count(*) AS star,count(n.v) AS c,sum(n.v) AS s,avg(n.v) AS a",
 "USE GRAPH 'g' MATCH (n:Report) RETURN collect(n.v) AS xs",
]
for q in qs:
 records=[('g','x','A',2),('other','x','A',9)] if q.startswith('MATCH') else []
 p=pr.Provider();sq=translate_to_sql(parse_query(q),{},engine=Caller(p));print('QUERY',q);print(sq.sql);print('PARAMS',sq.parameters)
 try:r,tr=execute(records,q);print(json.dumps(dict(raw=records,rows=r.rows,columns=r.columns,trace=tr),default=str))
 except Exception as e:print('PROVIDER-BOUNDARY',repr(e))
