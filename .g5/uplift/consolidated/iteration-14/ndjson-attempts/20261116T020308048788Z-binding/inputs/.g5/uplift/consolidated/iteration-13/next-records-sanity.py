"""Healthy ASCII record-hydration/export/import-reader feasibility, no model/native/Git/network.
Actual get_nodes/get_node/export_graph_ndjson/import_graph_ndjson bodies; SQLite SQL and CY_TYPED substitute.
Import writers record parsed arguments only: no claim of actual persistence or physical inverse.
"""
from pathlib import Path
import copy,hashlib,json,logging,os,socket,sqlite3,sys,time
logging.disable(logging.CRITICAL);socket.has_ipv6=False
sockets=[]
class Guard(socket.socket):
 def __new__(cls,*a,**k):sockets.append(str(a));raise AssertionError('socket prohibited')
socket.socket=Guard
socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'))
O=Path(__file__).resolve().parent;R=O.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
from iris_vector_graph._engine.nodes_edges import NodesEdgesMixin
from iris_vector_graph._engine.snapshot import SnapshotMixin

def typed(v):
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
  rows=self.c.fetchall();self.w.trace[-1]['raw_rows']=rows;return rows
 def close(self):self.closed=True;self.c.close()
class World:
 def __init__(self,nodes,labels,props,edges):
  self.trace=[];self.cursors=[];self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
  self.db.executescript('CREATE TABLE Graph_KG.nodes(graph_id TEXT,node_id TEXT,PRIMARY KEY(graph_id,node_id));CREATE TABLE Graph_KG.rdf_labels(graph_id TEXT,s TEXT,label TEXT);CREATE TABLE Graph_KG.rdf_props(graph_id TEXT,s TEXT,key TEXT,val);CREATE TABLE Graph_KG.rdf_edges(graph_id TEXT,edge_id INTEGER,s TEXT,p TEXT,o_id TEXT,qualifiers TEXT);')
  for name,arity,fn in [('CY_TYPED',1,typed),('STARTS',2,lambda x,p:int(x.startswith(p)) if x is not None else None)]:self.db.create_function(name,arity,fn)
  for table,rows,n in [('nodes',nodes,2),('rdf_labels',labels,3),('rdf_props',props,4),('rdf_edges',edges,6)]:self.db.executemany('INSERT INTO Graph_KG.'+table+' VALUES('+','.join('?' for _ in range(n))+')',rows)
 def cursor(self):c=Cursor(self);self.cursors.append(c);return c
class Engine(NodesEdgesMixin,SnapshotMixin):
 _ivg_schema='Graph_KG'
 def __init__(self,w):self.conn=w
 def _t(self,name):return 'Graph_KG.'+name
class Sink(SnapshotMixin):
 def __init__(self):self.calls=[]
 def create_node(self,id,labels=None,properties=None,graph=None):self.calls.append(dict(kind='node',id=id,labels=copy.deepcopy(labels),properties=copy.deepcopy(properties),graph=graph));return True
 def create_edge(self,s,p,o,**kwargs):self.calls.append(dict(kind='edge',source=s,predicate=p,target=o,kwargs=copy.deepcopy(kwargs)));return True

def decoded(v):
 if v=='true':return True
 if v=='false':return False
 if isinstance(v,str) and v[:1] in ('[','{'):
  try:x=json.loads(v)
  except ValueError:return v
  if isinstance(x,(list,dict)):return x
 return v

def hydrate(ids,graph,nodes,labels,props):
 output=[]
 for id in ids:
  ls=[label for g,s,label in labels if g==graph and s==id];ps=[(key,v) for g,s,key,v in props if g==graph and s==id]
  if not ls and not ps and (graph,id) not in nodes:continue
  record={'id':id,'labels':ls}
  for key,v in ps:record['p_'+key if key in ('id','labels') else key]=decoded(v)
  output.append(record)
 return output

def main():
 start=time.monotonic();nodes=[('','a'),('','b'),('','c'),('other','a')];labels=[('','a','Person'),('','a','Member'),('','b','City'),('other','a','Other')]
 props=[('','a','id','a'),('','a','labels','user-label'),('','a','name','Ann'),('','a','age',29),('','a','ratio',5.0),('','a','text','29'),('','a','active','true'),('','a','aliases','["A"]'),('other','a','name','Elsewhere')]
 edges=[('',10,'a','R','b','{"since":2020}'),('',11,'a','R','b',None),('',12,'a','Marked','b','{"temporal":true}'),('other',13,'a','R','a',None)]
 cases=[];output=O/'next-records-files';output.mkdir(exist_ok=True)
 for variant,extra in [('ordinary',[]),('known-alias-collision',[('','a','p_id','stored-p')])]:
  pp=props+extra;w=World(nodes,labels,pp,edges);e=Engine(w);ids=['b','a','b','absent','c']
  got=e.get_nodes(ids);want=hydrate(ids,'',nodes,labels,pp);assert got==want
  named=e.get_node('a',graph='other');assert named==hydrate(['a'],'other',nodes,labels,pp)[0]
  path=output/(variant+'.ndjson');export_cursor_index=len(w.cursors);counts=e.export_graph_ndjson(str(path));lines=path.read_text().splitlines();records=[json.loads(line) for line in lines]
  default_ids=sorted(id for g,id in nodes if g=='');hydrated=hydrate(default_ids,'',nodes,labels,pp)
  expected=[dict(kind='node',id=n['id'],labels=n['labels'],properties={k:v for k,v in n.items() if k not in ('id','labels')}) for n in hydrated]
  for g,edge_id,s,p,o,q in sorted(edges,key=lambda x:x[1]):
   if g!='' or q and q.startswith('{"temporal"'):continue
   item=dict(kind='edge',source=s,predicate=p,target=o);quals=json.loads(q) if q else None
   if quals:item['qualifiers']=quals
   expected.append(item)
  assert records==expected and counts==dict(nodes=3,edges=2) and len(lines)==counts['nodes']+counts['edges']
  sink=Sink();import_counts=sink.import_graph_ndjson(str(path))
  assert import_counts==dict(nodes=3,edges=2,temporal_edges=0,skipped=0)
  assert [c['properties'] for c in sink.calls if c['kind']=='node']==[n['properties'] for n in expected if n['kind']=='node']
  assert len([c for c in sink.calls if c['kind']=='edge'])==2
  cursor_closed=w.cursors[export_cursor_index].closed # export cursor precedes the nested hydration cursors
  assert cursor_closed
  cases.append(dict(variant=variant,raw=dict(nodes=nodes,labels=labels,props=pp,edges=edges),requested_ids=ids,hydrated=got,named=named,counts=counts,records=records,line_count=len(lines),file=str(path.relative_to(R)),file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),import_counts=import_counts,import_writer_arguments=sink.calls,source_projection_note='stored id reads p_id and exports as properties.p_id, not original raw id key; collisions follow delivered property-row order. No generic storage inverse.',trace=w.trace))
 assert not sockets
 inputs={}
 for rel in ['iris_vector_graph/_engine/nodes_edges.py','iris_vector_graph/_engine/snapshot.py','iris_vector_graph/_engine/ledger.py','iris_vector_graph/prop_values.py','iris_vector_graph/constants.py']:
  h=hashlib.sha256((PIN/rel).read_bytes()).hexdigest();assert h==hashlib.sha256((R/rel).read_bytes()).hexdigest();inputs[rel]=h
 out=dict(verdict='AGREES',healthy_fixtures=len(cases),actual_source_cases='Each fixture executes ordered/repeated/default hydrate, named hydrate, actual default export file, actual import parser dispatch.',cases=cases,inputs=inputs,socket_attempts=sockets,native_calls=0,Git_calls=0,elapsed_s=time.monotonic()-start,scope='Healthy ASCII raw rows only. SQLite executes selected source SQL, local CY_TYPED/STARTS scalar providers. Import writer callbacks record parsed fields, not actual persistence/transactions or inverse proof. Existing alias behavior, raw order/collation, JSON and native SQL providers qualified. No failure injection or forbidden next-phase work.')
 (O/'next-records-sanity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','healthy_fixtures','elapsed_s','socket_attempts','native_calls','Git_calls']}))
if __name__=='__main__':main()
