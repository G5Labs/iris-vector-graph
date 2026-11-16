"""Executing local SQL provider; no prepared query rows, Native API or actual import persistence."""
import json,sqlite3

def cy_typed(v):
 if type(v)is int:return '\x01N'+str(v)
 if type(v)is float:return '\x01D'+repr(v)
 if isinstance(v,str) and v.startswith('\x01'):return '\x01S'+v
 return v
class Cursor:
 def __init__(self,w):self.w=w;self.c=w.db.cursor();self.closed=False
 def execute(self,sql,args=()):
  adapted=sql.replace('Graph_KG.CY_TYPED(', 'CY_TYPED(').replace("qualifiers %STARTSWITH '{\"temporal\"'", "STARTS(qualifiers, '{\"temporal\"')")
  self.w.trace.append(dict(sql=sql,adapted=adapted,args=list(args)));self.c.execute(adapted,args);return self
 def fetchall(self):
  rows=self.c.fetchall();self.w.trace[-1]['rows']=rows;return rows
 def close(self):self.closed=True;self.c.close()
class World:
 def __init__(self,raw):
  self.trace=[];self.cursors=[];self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
  self.db.executescript('CREATE TABLE Graph_KG.nodes(graph_id TEXT,node_id TEXT,PRIMARY KEY(graph_id,node_id));CREATE TABLE Graph_KG.rdf_labels(graph_id TEXT,s TEXT,label TEXT);CREATE TABLE Graph_KG.rdf_props(graph_id TEXT,s TEXT,key TEXT,val);CREATE TABLE Graph_KG.rdf_edges(graph_id TEXT,edge_id INTEGER PRIMARY KEY,s TEXT,p TEXT,o_id TEXT,qualifiers TEXT);')
  self.db.create_function('CY_TYPED',1,cy_typed);self.db.create_function('STARTS',2,lambda x,p:int(x.startswith(p)) if x is not None else None)
  # Child rows follow the declared delivery order in this local provider. Normal raw keys are checked separately.
  for table,rows,n in [('nodes',raw['nodes'],2),('rdf_labels',raw['labels'],3),('rdf_props',raw['props'],4),('rdf_edges',raw['edges'],6)]:self.db.executemany('INSERT INTO Graph_KG.'+table+' VALUES('+','.join('?' for _ in range(n))+')',rows)
 def cursor(self):c=Cursor(self);self.cursors.append(c);return c
