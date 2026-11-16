"""Future ordinary introspection feasibility; no model/native/network/Git or fault injections."""
from pathlib import Path
import datetime,hashlib,json,logging,re,socket,sqlite3,sys,time
logging.disable(logging.CRITICAL);socket.has_ipv6=False
sockets=[]
class Guard(socket.socket):
 def __new__(cls,*a,**k):sockets.append(str(a));raise AssertionError('network prohibited')
socket.socket=Guard
socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'))
A=Path(__file__).resolve().parent;R=A.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
from iris_vector_graph._engine.nodes_edges import NodesEdgesMixin
from iris_vector_graph._engine.schema import SchemaMixin

def typed(v):
 if type(v)is int:return '\x01N'+str(v)
 if type(v)is float:return '\x01D'+repr(v)
 return '\x01S'+v if isinstance(v,str) and v.startswith('\x01') else v
class Cursor:
 def __init__(self,w):self.w=w;self.c=w.db.cursor()
 def execute(self,sql,args=()):
  adapted=sql.replace('Graph_KG.CY_TYPED(','CY_TYPED(');m=re.search(r'\bTOP\s+(\d+)\s+',adapted,re.I)
  if m:adapted=adapted[:m.start()]+adapted[m.end():]+' LIMIT '+m.group(1)
  self.entry=dict(sql=sql,adapted=adapted,args=list(args));self.w.trace.append(self.entry);self.c.execute(adapted,args);return self
 def fetchone(self):
  r=self.c.fetchone();self.entry.setdefault('delivered',[]).append(r);return r
 def fetchall(self):
  r=self.c.fetchall();self.entry['delivered']=r;return r
 def close(self):self.c.close()
class World:
 def __init__(self,raw):
  self.trace=[];self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
  self.db.executescript('CREATE TABLE Graph_KG.nodes(graph_id TEXT,node_id TEXT,PRIMARY KEY(graph_id,node_id));CREATE TABLE Graph_KG.rdf_labels(graph_id TEXT,s TEXT,label TEXT);CREATE TABLE Graph_KG.rdf_props(graph_id TEXT,s TEXT,key TEXT,val);CREATE TABLE Graph_KG.rdf_edges(graph_id TEXT,edge_id INTEGER,s TEXT,p TEXT,o_id TEXT,qualifiers TEXT);')
  self.db.create_function('CY_TYPED',1,typed)
  for table,arity in [('nodes',2),('rdf_labels',3),('rdf_props',4),('rdf_edges',6)]:self.db.executemany('INSERT INTO Graph_KG.'+table+' VALUES('+','.join('?' for _ in range(arity))+')',raw[table])
 def cursor(self):return Cursor(self)
class Engine(NodesEdgesMixin,SchemaMixin):
 _ivg_schema='Graph_KG'
 def __init__(self,w):self.conn=w
 def _t(self,n):return 'Graph_KG.'+n

def main():
 start=time.monotonic();raw=dict(nodes=[('','a'),('','b'),('other','a'),('other','n'),('onlynodes','z')],rdf_labels=[('','a','Person'),('other','a','Other'),('other','a','Person'),('other','n','Person'),('','b','City'),('onlynodes','z','BareLabel')],rdf_props=[('','a','id','a'),('','a','name','Ann'),('','a','age',29),('other','a','named_key','Named'),('other','n','only_named','N'),('','b','city','City')]+[('','a',f'key{i:02d}','value') for i in range(22)],rdf_edges=[('',1,'a','R','b',None),('',2,'a','R','b',None),('other',3,'n','R','a',None),('other',4,'a','S','n',None)])
 cases=[]
 for name,data in [('healthy-populated',raw),('healthy-empty',{k:[] for k in raw})]:
  w=World(data);e=Engine(w);labels=e.get_labels();preds=e.get_relationship_types();keys=e.get_property_keys();person=e.get_property_keys('Person');none=e.get_property_keys('Missing');graphs=e.list_graphs();ids=e.get_node_ids_by_label('Person');hydrated=e.get_nodes_by_label('Person');diagram=e.get_schema_visualization()
  assert labels==sorted({x[2] for x in data['rdf_labels']});assert preds==sorted({x[4] for x in data['rdf_edges']});assert keys==sorted({x[2] for x in data['rdf_props']});assert graphs==sorted({x[0] for x in data['rdf_edges'] if x[0]});assert none==[]
  subject_ids={s for g,s,l in data['rdf_labels'] if l=='Person'};want_keys=sorted({k for g,s,k,v in data['rdf_props'] if s in subject_ids});assert person==want_keys
  assert ids==[s for g,s,l in data['rdf_labels'] if l=='Person' and s]
  if name=='healthy-populated':
   assert ids==['a','a','n'];assert len(hydrated)==2 and all(n['id']=='a' and n['labels']==['Person'] for n in hydrated)
   assert 'named_key' in person and 'only_named' in person
   assert not any('named_key' in n or 'only_named' in n for n in hydrated)
   p=next(n for n in diagram['nodes'] if n['name']=='Person');assert len(p['properties'])==20 and 'named_key' not in {x['name'] for x in p['properties']}
   assert [n['name'] for n in diagram['nodes']]==labels
   assert [x['name'] for x in diagram['relationships']]==preds
  else:assert diagram==dict(nodes=[],relationships=[]) and not hydrated
  cases.append(dict(name=name,raw=data,labels=labels,predicates=preds,keys=keys,person_keys=person,named_graphs_with_edges=graphs,label_ids=ids,label_hydrated=hydrated,diagram=diagram,trace=w.trace))
 # Neighbor holding labels fixed changes arbitrary sample-row order and hence sampled content;
 # local SQLite provider order is observed only, not an IRIS no-ORDER-BY guarantee.
 other={k:list(v) for k,v in raw.items()};other['rdf_labels']=[('other','a','Person')]+[x for x in raw['rdf_labels'] if x!=('other','a','Person')];other['rdf_props']=[('other','a','aaa_named_first','X')]+list(raw['rdf_props']);w=World(other);diagram=Engine(w).get_schema_visualization();person=next(n for n in diagram['nodes'] if n['name']=='Person');assert person['properties'][0]['name']=='aaa_named_first'
 cases.append(dict(name='healthy-sample-content-neighbor',raw=other,diagram=diagram,trace=w.trace,qualification='firstrow provider order not universal; same-ID properties deliberately read across graphs in source diagram'))
 assert not sockets
 files=['iris_vector_graph/_engine/schema.py','iris_vector_graph/_engine/nodes_edges.py','iris_vector_graph/prop_values.py'];hashes={}
 for f in files:
  hashes[f]=hashlib.sha256((R/f).read_bytes()).hexdigest();assert hashes[f]==hashlib.sha256((PIN/f).read_bytes()).hexdigest()
 out=dict(verdict='AGREES_AS_BUILT_ORDINARY_ONLY',cases=cases,input_source_sha256=hashes,fixture_count=3,socket_attempts=sockets,native_calls=0,Git_calls=0,elapsed_s=time.monotonic()-start,formal_or_issue_credit=0,limits='Source-informed future survey only; actual public Python with local executing SQL and TOP-to-LIMIT/CY_TYPED providers. No native order/collation/connection protocol/failure claims, no model or inverse, no adjudication of graph policy or new issue. No interrupted inputs/outcomes.')
 (A/'next-introspection-sanity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','fixture_count','socket_attempts','native_calls','Git_calls','elapsed_s']}))
if __name__=='__main__':main()
