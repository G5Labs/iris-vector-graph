"""Actual C15 Python readers over derived census pages and executing local SQLite."""
import hashlib,json,logging,socket,sqlite3,sys,time,types
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.dont_write_bytecode=True
logging.disable(logging.CRITICAL);start=time.perf_counter();cases=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('paging probe forbids sockets')) as guard:
 sys.path.insert(0,str(PIN));from iris_vector_graph import _edgeless
 from iris_vector_graph._engine.algorithms import AlgorithmsMixin
 class Native:
  def __init__(self,nodes,edges,mode):self.nodes=nodes;self.edges=edges;self.mode=mode;self.calls=[]
  def classMethodValue(self,cls,method,schema,graph,after,limit):
   self.calls.append(dict(cls=cls,method=method,schema=schema,graph=graph,after=after,limit=limit));assert (cls,method)==('Graph.KG.Edgeless','LonersJson')
   if len(self.calls)==2 and self.mode=='fail':raise RuntimeError('named second-page provider unavailable')
   if len(self.calls)==2 and self.mode=='malformed':return 'not-json'
   # One page derived from raw node membership and mirrored selected raw coordinates.
   live=[v for v in sorted(self.nodes) if v>after and not any(a!=b and v in (a,b) for a,p,b in self.edges)]
   page=live[:limit] if limit>0 else live;loops={v:int(any(a==v for a,p,b in self.edges)) for v in page}
   return json.dumps(dict(loners=loops,next=page[-1] if limit>0 and len(page)==limit else ''))
 class Cursor:
  def __init__(self,c):self.c=c;self.cur=c.db.cursor()
  def execute(self,sql,args):
   self.c.queries.append(dict(sql=sql,args=args))
   if self.c.fail:raise sqlite3.OperationalError('named SQL census unavailable')
   self.cur.execute(sql,args)
  def fetchall(self):return self.cur.fetchall()
  def close(self):self.cur.close()
 class Conn:
  def __init__(self,nodes,edges,fail=False):
   self.db=sqlite3.connect(':memory:');self.queries=[];self.fail=fail
   self.db.execute('CREATE TABLE nodes(node_id TEXT,graph_id TEXT)');self.db.execute('CREATE TABLE rdf_edges(s TEXT,p TEXT,o_id TEXT,graph_id TEXT)')
   self.db.executemany('INSERT INTO nodes VALUES(?,?)',[(v,'') for v in nodes]);self.db.executemany('INSERT INTO rdf_edges VALUES(?,?,?,?)',[(a,p,b,'') for a,p,b in edges])
  def cursor(self):return Cursor(self)
 def oracle(nodes,edges):return {v:any(a==v for a,p,b in edges) for v in nodes if not any(a!=b and v in (a,b) for a,p,b in edges)}
 nodes=['a','b','iso','loop'];edges=[('a','R','b'),('loop','L','loop')];real=_edgeless.loners
 for mode in ['good','fail','malformed','double-failure','empty']:
  ns=['a','b'] if mode=='empty' else nodes;es=[('a','R','b')] if mode=='empty' else edges;n=Native(ns,es,'fail' if mode=='double-failure' else mode);c=Conn(ns,es,mode=='double-failure')
  e=types.SimpleNamespace(conn=c,_t=lambda table:'main.'+table,_iris_obj=lambda:n)
  got,error=None,None
  # Explicit helper page parameter substitution only; actual helper and dispatch bodies unchanged.
  with patch.object(_edgeless,'loners',side_effect=lambda native,schema,graph:real(native,schema,graph,page=1)):
   try:got=AlgorithmsMixin._loners(e)
   except Exception as ex:error=dict(type=type(ex).__name__,message=str(ex))
  if mode=='double-failure':okay=got is None and error['type']=='OperationalError' and len(n.calls)==2 and len(c.queries)==1
  elif mode=='empty':okay=got=={} and error is None and len(n.calls)==1 and len(c.queries)==0
  elif mode=='good':okay=got==oracle(ns,es) and error is None and len(n.calls)==3 and len(c.queries)==0 and [x['after'] for x in n.calls]==['','iso','loop']
  else:okay=got==oracle(ns,es) and error is None and len(n.calls)==2 and len(c.queries)==1
  assert okay,(mode,got,error,n.calls,c.queries)
  cases.append(dict(mode=mode,raw_nodes=ns,raw_edges=es,actual=got,error=error,native_page_calls=n.calls,sql=c.queries,agrees=True));c.db.close()
 assert guard.call_count==0
 sources={p:hashlib.sha256((PIN/p).read_bytes()).hexdigest() for p in ['iris_vector_graph/_edgeless.py','iris_vector_graph/_engine/algorithms.py']};assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in sources.items())
 out=dict(verdict='ACTUAL_PAGING_DISPATCH_SQL_SOURCE_AGREES',cases=cases,socket_connect_calls=0,native_calls=0,source_inputs=sources,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),elapsed_s=time.perf_counter()-start,helper_substitution='Actual _edgeless.loners invoked with explicit supported page=1 through dispatch wrapper; named raw Native port derives each page from raw membership/edges. SQLite executes actual SQL. No native class or server call.',scope='Five frozen C15 neighboring source/provider cases, not new sampling/grade/formal units. Native/SQL projection uses a stated faithful raw fixture. SQLite parameter behavior does not prove native DBAPI semantics; root8 is separate finite corroboration.')
 (HERE/'review-communities-paging-probe.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],cases=5,sockets=0,native=0,seconds=out['elapsed_s'])))
