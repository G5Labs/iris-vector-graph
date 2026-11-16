"""Executing SQLite provider for the emitted SQL fragment, never precomputed result rows.
IRIS SQL functions, collation and byte codecs are explicit local substitutions, not native execution.
"""
import json,re,sqlite3

def cy_typed(v):
 if type(v) is int:return '\x01N'+str(v)
 if type(v) is float:return '\x01D'+repr(v)
 if isinstance(v,str) and v.startswith('\x01'):return '\x01S'+v
 return v
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
  for name,arity,fn in [('EXACT',1,lambda x:x),('CY_TYPED',1,cy_typed),('CY_IS_FLOAT',1,lambda x:int(type(x)is float)),('CY_SORT_KEY',2,lambda x,k:x),('CY_JSON_NUM',1,lambda x:json.dumps(x) if x is not None else None),('CY_JSON_ESC',1,lambda x:json.dumps(str(x)) if x is not None else 'null')]:self.db.create_function(name,arity,fn)
  self.db.create_aggregate('JSON_ARRAYAGG',1,ArrayAgg);self.db.create_aggregate('LIST',1,ListAgg)
  self.db.executescript('CREATE TABLE nodes(graph_id TEXT,node_id TEXT,PRIMARY KEY(graph_id,node_id));CREATE TABLE rdf_labels(graph_id TEXT,s TEXT,label TEXT);CREATE TABLE rdf_props(graph_id TEXT,s TEXT,key TEXT,val);CREATE TABLE rdf_edges(graph_id TEXT,s TEXT,p TEXT,o TEXT,edge_id TEXT);')
 def cursor(self):return Cursor(self)
 def load(self,records,edges=()):
  for graph,id,key,value in records:
   self.db.execute('INSERT INTO nodes VALUES(?,?)',(graph,id));self.db.execute('INSERT INTO rdf_labels VALUES(?,?,?)',(graph,id,'Report'))
   if key is not None:self.db.execute('INSERT INTO rdf_props VALUES(?,?,?,?)',(graph,id,'k',key))
   if value is not None:self.db.execute('INSERT INTO rdf_props VALUES(?,?,?,?)',(graph,id,'v',value))
  for row in edges:self.db.execute('INSERT INTO rdf_edges VALUES(?,?,?,?,?)',row)
