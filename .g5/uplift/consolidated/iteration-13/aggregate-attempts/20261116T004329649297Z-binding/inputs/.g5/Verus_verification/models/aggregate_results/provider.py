"""Executing SQLite provider for the emitted SQL fragment, never precomputed result rows.
IRIS SQL functions, collation and byte codecs are explicit local substitutions, not native execution.
"""
import json,re,sqlite3

def cy_typed(v):
 if type(v) is int:return '\x01N'+str(v)
 if type(v) is float:return '\x01D'+repr(v)
 if isinstance(v,str) and v.startswith('\x01'):return '\x01S'+v
 return v
def json_number(x):return json.dumps(x) if type(x) in (int,float) else None
def json_listmap(x):
 if not isinstance(x,str):return None
 try:v=json.loads(x)
 except ValueError:return None
 return x if isinstance(v,(list,dict)) else None
class CanonicalSum:
 """IRIS canonical decimal SUM carrier substituted over exact half-unit inputs; DOUBLE CAST stays SQLite REAL."""
 def __init__(self):self.total=0;self.count=0
 def step(self,v):
  if v is not None:self.total+=v;self.count+=1
 def finalize(self):return None if self.count==0 else int(self.total) if float(self.total).is_integer() else self.total
class CanonicalAvg(CanonicalSum):
 def finalize(self):
  if not self.count:return None
  v=self.total/self.count
  return int(v) if float(v).is_integer() else v
class ArrayAgg:
 def __init__(self):self.values=[]
 def step(self,v):
  if v is not None:self.values.append(v)
 def finalize(self):return json.dumps(self.values,separators=(',',':'))
class ListAgg:
 def __init__(self):self.values=[]
 def step(self,v):
  if v is not None:self.values.append(str(v))
 def finalize(self):return ','.join(self.values) if self.values else None

def sql_adapter(sql):
 sql=sql.replace('Graph_KG.','').replace('%EXACT(', 'EXACT(')
 for hint in ['%IGNOREINDEX','%NOINDEX','%PARALLEL','%NOPARALLEL']:sql=sql.replace(hint,'')
 m=re.match(r'SELECT TOP (\d+) ',sql)
 if m:sql='SELECT '+sql[m.end():]+' LIMIT '+m.group(1)
 sql=re.sub(r"TRIM\(TRAILING '\]' FROM SUBSTRING\(JSON_ARRAY\((EXACT\(p\d+\.val\)|p\d+\.val)\), 2\)\)",r"RTRIM(SUBSTR(JSON_ARRAY(\1), 2), ']')",sql)
 sql=re.sub(r'FETCH FIRST (\d+) ROWS ONLY',r'LIMIT \1',sql)
 return sql
class Cursor:
 def __init__(self,owner):self.owner=owner;self.cur=owner.db.cursor()
 def execute(self,sql,params=()):
  adapted=sql_adapter(sql);self.owner.trace.append(dict(source=sql,adapted=adapted,params=list(params)))
  self.cur.execute(adapted,params);return self
 @property
 def description(self):return self.cur.description
 def fetchall(self):return self.cur.fetchall()
 def fetchone(self):return self.cur.fetchone()
 def close(self):self.cur.close()
class Provider:
 def __init__(self):
  self.db=sqlite3.connect(':memory:');self.trace=[]
  for name,arity,fn in [('EXACT',1,lambda x:x),('CY_TYPED',1,cy_typed),('CY_IS_FLOAT',1,lambda x:int(type(x)is float)),('CY_SORT_KEY',2,lambda x,k:x),('CY_JSON_NUM',1,json_number),('CY_JSON_LISTMAP',1,json_listmap),('CY_JSON_ESC',1,lambda x:json.dumps(str(x)) if x is not None else 'null')]:self.db.create_function(name,arity,fn)
  self.db.create_aggregate('SUM',1,CanonicalSum);self.db.create_aggregate('AVG',1,CanonicalAvg);self.db.create_aggregate('JSON_ARRAYAGG',1,ArrayAgg);self.db.create_aggregate('LIST',1,ListAgg)
  self.db.executescript('CREATE TABLE nodes(graph_id TEXT,node_id TEXT,PRIMARY KEY(graph_id,node_id));CREATE TABLE rdf_labels(graph_id TEXT,s TEXT,label TEXT);CREATE TABLE rdf_props(graph_id TEXT,s TEXT,key TEXT,val);CREATE TABLE rdf_edges(graph_id TEXT,s TEXT,p TEXT,o_id TEXT,edge_id TEXT);')
 def cursor(self):return Cursor(self)
 def load(self,records,edges=()):
  for graph,id,key,value in records:
   self.db.execute('INSERT INTO nodes VALUES(?,?)',(graph,id));self.db.execute('INSERT INTO rdf_labels VALUES(?,?,?)',(graph,id,'Report'))
   if key is not None:self.db.execute('INSERT INTO rdf_props VALUES(?,?,?,?)',(graph,id,'k',key))
   if value is not None:self.db.execute('INSERT INTO rdf_props VALUES(?,?,?,?)',(graph,id,'v',value))
  for row in edges:self.db.execute('INSERT INTO rdf_edges VALUES(?,?,?,?,?)',row)
