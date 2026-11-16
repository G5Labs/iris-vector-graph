#!/usr/bin/env python3
"""Pinned actual census/scoped SQL and final report over executing local tables.
Native/index/schema providers are explicit substitutes, not native-body evidence.
"""
import ast, contextlib, dataclasses, hashlib, inspect, itertools, json, os, re, socket, sqlite3, sys, textwrap, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PIN=Path(os.environ.get('IVG_PIN_DIR','/Users/ziniuw/runs/ivg-consolidated-20261114/pin'))
sys.path.insert(0,str(PIN))
SOCKETS=[]
def no_socket(*a,**kw): SOCKETS.append('connect');raise AssertionError('socket forbidden')
socket.socket.connect=no_socket;socket.create_connection=no_socket
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.status import EngineStatus,ArnoStatus,STATUS_PARTS
from iris_vector_graph.schema import GraphSchema
from iris_vector_graph._engine import admin
from iris_vector_graph._engine.nodes_edges import NodesEdgesMixin
from iris_vector_graph._engine.schema import SchemaMixin
SOURCES=['iris_vector_graph/engine.py','iris_vector_graph/_engine/admin.py','iris_vector_graph/_engine/schema.py','iris_vector_graph/_engine/nodes_edges.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/status.py','iris_vector_graph/security.py','iris_vector_graph/_validate.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
SOURCE_INPUTS={s:{'pin_sha256':sha(PIN/s),'current_sha256':sha(REPO/s)} for s in SOURCES}
assert all(v['pin_sha256']==v['current_sha256'] for v in SOURCE_INPUTS.values())
CORE=['nodes','rdf_edges','rdf_labels','rdf_props'];LEG={'node':'kg_NodeEmbeddings','edge':'kg_EdgeEmbeddings'}
N='kg_emb_'+'1'*16;N2='kg_emb_'+'2'*16;E='kg_eemb_'+'3'*16
class Cursor:
 def __init__(self,p):self.p=p;self.c=p.db.cursor();self.sql=''
 def execute(self,sql,params=None):
  self.sql=str(sql);self.p.queries.append((self.sql,list(params or [])))
  name=re.search(r'FROM\s+Graph_KG\.([\w]+)',self.sql,re.I)
  if name and name[1] in self.p.refused:raise RuntimeError(getattr(self.p,'shared_diagnostic',None) or 'provider refused '+name[1])
  if name and name[1]=='embedding_registry' and self.p.reg_error:raise RuntimeError(self.p.reg_error)
  try:self.c.execute(sql,params or [])
  except sqlite3.OperationalError as exc:
   if 'no such table' in str(exc):raise RuntimeError('SQLCODE: <-30> '+str(exc)) from exc
   raise
  return self
 def fetchone(self):
  if self.p.fetch_fail and self.p.fetch_fail in self.sql:raise RuntimeError('fetch failed')
  return self.c.fetchone()
 def fetchall(self):
  rows=self.c.fetchall();self.p.returned.append({'sql':self.sql,'rows':rows});return rows
 def close(self):self.c.close()
class Provider:
 def __init__(self,tables,routes=(),registry=True,reg_error=None,refused=(),fetch_fail=None):
  self.tables=tables;self.routes=list(routes);self.registry=registry;self.reg_error=reg_error;self.refused=set(refused);self.fetch_fail=fetch_fail;self.queries=[];self.returned=[]
  self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
  for table,rows in tables.items():
   self.db.execute(f'CREATE TABLE Graph_KG.{table}(graph_id TEXT,node_id TEXT,s TEXT,p TEXT,o_id TEXT,label TEXT,value TEXT)')
   self.db.executemany(f'INSERT INTO Graph_KG.{table} VALUES(?,?,?,?,?,?,?)',[(r.get('graph'),r.get('id','a'),r.get('id','a'),r.get('pred','R'),r.get('dst','b'),r.get('label','L'),r.get('value','x')) for r in rows])
  if registry:
   self.db.execute('CREATE TABLE Graph_KG.embedding_registry(table_name TEXT,kind TEXT,graph_id TEXT)')
   self.db.executemany('INSERT INTO Graph_KG.embedding_registry VALUES(?,?,?)',[(n,k,str(i)) for i,(n,k) in enumerate(routes)])
 def cursor(self):return Cursor(self)
 def close(self):self.db.close()
class Native:
 def classMethodValue(self,cls,method,*args):return 0
 def isDefined(self,*a):return 0
 def nextSubscript(self,*a):return ''
def engine(p):
 e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';e.embedding_dimension=4;e._nkg_dirty=False;e._schema_guard=None
 e._capabilities=SimpleNamespace(objectscript_deployed=False);e._arno_available=False;e._arno_capabilities={}
 e._iris_obj=lambda:Native();e._native_or_none=lambda:None;e._detect_arno=lambda:False
 e._missing_routines=lambda cursor,errors,unknown:[];e._ledger_status=lambda errors:None
 return e
@contextlib.contextmanager
def ancillary(hnsw=False):
 with contextlib.ExitStack() as stack:
  stack.enter_context(patch.object(GraphSchema,'adjacency_index_kind',return_value='functional'))
  stack.enter_context(patch.object(GraphSchema,'hnsw_indexes',return_value=['fixture_index'] if hnsw else []))
  stack.enter_context(patch('iris_vector_graph.schema._call_classmethod',return_value=''))
  stack.enter_context(patch.object(admin,'_degree_cache_off',return_value=[]))
  stack.enter_context(patch.object(admin,'arno_status',return_value=ArnoStatus()))
  yield
# Independent oracle selects physical names by finite string structure, then scans raw rows.
def admissible(name,kind):
 prefix={'node':'kg_emb_','edge':'kg_eemb_'}[kind]
 return isinstance(name,str) and len(name)==len(prefix)+16 and name[:len(prefix)]==prefix and all(ch in '0123456789abcdef' for ch in name[len(prefix):])
def oracle(p):
 out={};errors=set();unknown=set()
 for field,t in zip(['nodes','edges','labels','props'],CORE):
  failed=t not in p.tables or t in p.refused or (p.fetch_fail and p.fetch_fail in 'SELECT COUNT(*) FROM Graph_KG.'+t)
  out[field]=0 if failed else len(p.tables[t])
  if failed:
   errors.add('count:'+t)
   if field in ('nodes','edges'):unknown.add('graph')
 for kind,field in [('node','node_embeddings'),('edge','edge_embeddings')]:
  names={LEG[kind]};reg_error=None
  if p.registry and not p.reg_error:
   names|={n for n,k in p.routes if (k or 'node')==kind and admissible(n,kind)}
  elif p.reg_error and 'SQLCODE: <-30>' not in p.reg_error:
   reg_error='registry';errors.add(reg_error)
  failed=False;total=0
  for n in sorted(names):
   if n in p.tables and n not in p.refused and not (p.fetch_fail and p.fetch_fail in 'SELECT COUNT(*) FROM Graph_KG.'+n):total+=len(p.tables[n])
   else:failed=True;errors.add('count:'+n)
  out[field]=total
  if kind=='node' and (reg_error or failed):unknown.add('vector_index')
 return out,errors,unknown
def error_tags(status):
 out=set()
 for e in status.errors:
  if e.startswith('embedding registry read failed'):out.add('registry')
  elif e.startswith('count probe failed for '):out.add('count:'+e.split('count probe failed for ',1)[1].split(':',1)[0])
  elif e.startswith('count probe failed:'):
   # Provider diagnostics explicitly identify table when relevant; execute errors include sqlite table name.
   match=re.search(r'(nodes|rdf_edges|rdf_labels|rdf_props)',e)
   if match:out.add('count:'+match[1])
   elif 'fetch failed' in e:out.add('count:fetch')
   else:raise AssertionError(e)
  else:raise AssertionError(('unmodeled ancillary error',e))
 return out
COMPARISONS=0;CASES=[]
def check(a,b,why):
 global COMPARISONS;COMPARISONS+=1
 assert a==b,(why,a,b)
def run_world(tables,routes=(),registry=True,reg_error=None,refused=(),label='world'):
 p=Provider(tables,routes,registry,reg_error,refused);e=engine(p)
 try:
  with ancillary():s=e.status()
  expected,errors,unknown=oracle(p)
  check(dataclasses.asdict(s.tables),expected,label+' tables')
  check(set(s.unknown),unknown,label+' unknown')
  check(error_tags(s),errors,label+' errors')
  check(len(s.errors),len(set(s.errors)),label+' dedup')
  graphline=next(x.strip() for x in s.report().splitlines() if x.startswith('Graph:'))
  want='unknown (see Probe errors)' if 'graph' in unknown else f"{expected['nodes']:,} nodes · {expected['edges']:,} edges in every graph"
  check(want in graphline,True,label+' final report')
  check(s.adjacency.kg_edge_count,0,label+' cached/raw independence')
  if errors:check('Probe errors' in s.report(),True,label+' errors visible')
  for k in ['node','edge']:
   errs=[];actual=e._embedding_tables(p.cursor(),k,errs)
   want=[LEG[k]]
   if registry and not reg_error:
    for n,kind in routes:
     if (kind or 'node')==k and admissible(n,k) and n.lower() not in {x.lower() for x in want}:want.append(n)
   check(actual,want,label+' selected '+k)
  for g in [None,'','g','other']:
   gid=g or ''
   for method,table in [('node_count','nodes'),('edge_count','rdf_edges')]:
    if table in tables and table not in refused:
     check(getattr(e,method)(g),sum((r.get('graph') or '')==gid for r in tables[table]),label+method+str(g))
   for f in [None,'','L','Z']:
    table='rdf_labels' if f else 'nodes'
    if table in tables and table not in refused:
     expected_count=sum((r.get('graph') or '')==gid and (not f or r.get('label','L')==f) for r in tables[table])
     check(e.count_nodes(f,g),expected_count,label+' count_nodes')
     check(e.get_node_count(f,g),expected_count,label+' get_node_count')
   for f in [None,'','R','Z']:
    if 'rdf_edges' in tables and 'rdf_edges' not in refused:
     check(e.get_edge_count(f,g),sum((r.get('graph') or '')==gid and (not f or r.get('pred','R')==f) for r in tables['rdf_edges']),label+' get_edge_count')
   if 'rdf_labels' in tables and 'rdf_labels' not in refused:
    counts={}
    for r in tables['rdf_labels']:
     if (r.get('graph') or '')==gid:counts[r.get('label','L')]=counts.get(r.get('label','L'),0)+1
    distribution=e.get_label_distribution(g)
    check(distribution,counts,label+' grouped labels')
    check(list(distribution.values()),sorted(counts.values(),reverse=True),label+' descending group count')
  CASES.append({'name':label,'tables':expected,'unknown':sorted(unknown),'errors':sorted(errors),'queries':len(p.queries),'registry_rows':[x for x in p.returned if 'SELECT DISTINCT table_name' in x['sql']]})
  return dataclasses.asdict(s.tables),s.report()
 finally:p.close()
def main():
 start=time.monotonic()
 rows=[{'graph':None,'id':'a','label':'L'},{'graph':'','id':'b','label':'L'}, {'graph':'g','id':'a','label':'Z'},{'graph':'g','id':'c','label':'L'}]
 base={t:list(rows) for t in CORE};base[LEG['node']]=rows[:1];base[LEG['edge']]=rows[:2];base['kg_NodeEmbeddings_optimized']=rows*3
 # Crossed raw row populations, routes and absent/failure catalogs; never supplied counts.
 variants=[[],rows[:1],rows[:2],rows,rows+rows[:1],list(reversed(rows))]
 panels=[([],{}), ([(N,'node'),(N2,'node'),(E,'edge')],{N:rows[:2],N2:rows,E:rows[:1]}), ([(N,None),(N,'node'),(N,''),(N,'edge'),('not_a_route','node')],{N:rows}), ([(N,'edge'),(E,'node')],{N:rows,E:rows})]
 for i,(nr,er,lr) in enumerate(itertools.product(variants[:4],variants[:3],variants[:3])):
  for j,(routes,extra) in enumerate(panels):
   tables={**base,**extra,'nodes':nr,'rdf_edges':er,'rdf_labels':lr}
   run_world(tables,routes,label=f'raw-{i}-{j}')
 special=[('absent-reg',{},[],False,None,()),('unreadable-reg',{},[],True,'provider denied registry',()),('missing-route',{},[(N,'node'),(E,'edge')],True,None,()),('missing-node',{'nodes':None},[],True,None,()),('missing-labels',{'rdf_labels':None},[],True,None,()),('missing-props',{'rdf_props':None},[],True,None,()),('node-vector-refused',{},[],True,None,(LEG['node'],)),('missing-edge-vectors',{LEG['edge']:None},[],True,None,()),('refused-edge',{},[],True,None,('rdf_edges',)),('edge-only-failure',{},[(E,'edge')],True,None,()),('mixed-partial', {N:rows},[(N,'node'),(N2,'node')],True,None,())]
 for label,change,routes,registry,reg_error,refused in special:
  t={**base,**change};t={k:v for k,v in t.items() if v is not None};run_world(t,routes,registry,reg_error,refused,label)
 # Positive derived vector count plus explicit index provider reaches the final indexed label.
 p=Provider(base);e=engine(p)
 with ancillary(True):s=e.status()
 check(s.tables.node_embeddings,len(base[LEG['node']]),'indexed raw census');check(f"({s.tables.node_embeddings:,} indexed)" in s.report(),True,'indexed final reader');p.close()
 # Identical raw diagnostics are merged only by the real final wrapper/dedup.
 p=Provider(base,refused=['nodes','rdf_edges']);p.shared_diagnostic='shared outage';e=engine(p)
 with ancillary():s=e.status()
 check(s.errors,['count probe failed: shared outage'],'same-message core dedup');check(s.unknown,['graph'],'same-message graph unknown');check('unknown' in next(x for x in s.report().splitlines() if x.startswith('Graph:')),True,'same-message consumer');p.close()
 p=Provider(base,fetch_fail='Graph_KG.nodes');e=engine(p)
 with ancillary():s=e.status()
 check(s.tables.nodes,0,'fetch failure fallback');check(s.tables.edges,len(base['rdf_edges']),'later field still read');check(s.errors,['count probe failed: fetch failed'],'fetch error wrapper');check('graph' in s.unknown,True,'fetch error unknown');p.close()
 # All scoped failures propagate instead of fabricated empty counts.
 p=Provider(base,refused=['nodes','rdf_edges','rdf_labels']);e=engine(p)
 for name,args in [('node_count',()),('edge_count',()),('count_nodes',()),('get_node_count',()),('get_edge_count',()),('get_label_distribution',())]:
  try:getattr(e,name)(*args)
  except RuntimeError:check(True,True,'scalar failure '+name)
  else:raise AssertionError(name+' swallowed failure')
 for name in ['node_count','edge_count','count_nodes','get_node_count','get_edge_count','get_label_distribution']:
  old=len(p.queries)
  try:getattr(e,name)(graph='0')
  except ValueError:check(len(p.queries),old,'graph refusal before SQL')
  else:raise AssertionError('bad graph accepted')
 p.close()
 # Actual public refusal branch must not perform census.
 p=Provider(base);e=engine(p);e._status_schema=lambda:('Graph_KG','namespace refused',0,None)
 with ancillary():s=e.status()
 check(p.queries,[],'refusal no SQL');check(set(s.unknown),set(STATUS_PARTS),'refusal parts');check('unknown' in s.report(),True,'refusal report');p.close()
 detections=sensitivity(base,rows)
 print(json.dumps({'sensitivity_observations':detections},sort_keys=True));check(all(detections.values()),True,'all genuine effects detected');check(SOCKETS,[],'zero sockets')
 out={'verdict':'AGREES','worlds':len(CASES),'comparisons':COMPARISONS,'sensitivities':detections,'socket_attempts':len(SOCKETS),'seconds':time.monotonic()-start,'source_inputs':SOURCE_INPUTS,'package_inputs':{p.name:sha(p) for p in HERE.iterdir() if p.is_file()},'cases':CASES}
 target=REPO/'.g5/Verus_verification/results/routine_reporting'/time.strftime('%Y%m%dT%H%M%SZ-binding',time.gmtime());target.mkdir(parents=True,exist_ok=True);(target/'binding.json').write_text(json.dumps(out,indent=2)+'\n')
 flat={str(p.relative_to(REPO)):sha(p) for p in HERE.iterdir() if p.is_file()}
 flat.update({s:sha(REPO/s) for s in SOURCES})
 for name in ['reporting-attempt.py','reporting-upstream.py','reporting-PAIRS.md','reporting-roles.json']:
  p=REPO/'.g5/uplift/consolidated/iteration-13'/name;flat[str(p.relative_to(REPO))]=sha(p)
 receipt={'kind':'binding','model':'routine_reporting','product_baseline':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','python':sys.version.split()[0],
  'inputs':flat,'verdict':out['verdict'],'comparisons':COMPARISONS,'mismatch_count':0,'socket_connect_calls':len(SOCKETS),'native_executions':0,
  'worlds':len(CASES),'sensitivity':detections,'elapsed':out['seconds'],'detail':'binding.json','detail_sha256':sha(target/'binding.json'),
  'identity':'selected current source SHA256 equals immutable public pin export; no Git invocation',
  'scope':'Actual pinned census/scoped/grouped SQL and human report over executing SQLite, independent raw-row oracle; source/SQL/native provider limits in NOTES.'}
 (target/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps({k:v for k,v in out.items() if k not in ('cases','source_inputs','package_inputs')},indent=2))
def mutated(cls,name,old,new):
 fn=getattr(cls,name);source=textwrap.dedent(inspect.getsource(fn));assert source.count(old)==1,(name,old,source.count(old));source=source.replace(old,new)
 ns={};exec(compile(source,'<localized reporting source mutation>','exec'),fn.__globals__,ns);return ns[name]
def sensitivity(base,rows):
 # Every alteration runs an actual selected product method and compares final public observations.
 results={};fixture={**base,N:rows[:2],N2:rows[:1]};routes=[(N,'node'),(N,''),(N2,'node')]
 original=run_world(fixture,routes,label='sensitivity-baseline')
 cases=[('all-graphs-leak',NodesEdgesMixin,'_count_in_graph'," WHERE COALESCE(graph_id, '') = ?",'', 'scope'),
 ('route-kind-ignored',type_base('_embedding_tables'),'_embedding_tables','row_kind != kind or ','','kind'),
 ('route-dedup-removed',type_base('_embedding_tables'),'_embedding_tables',' or name.lower() in seen','','sum'),
 ('legacy-omitted',type_base('_embedding_tables'),'_embedding_tables','tables = [legacy]','tables = []','sum'),
 ('sum-overwritten',type_base('_embedding_row_count'),'_embedding_row_count','total += int(row[0]) if row else 0','total = int(row[0]) if row else 0','sum'),
 ('registry-error-silent',type_base('_embedding_tables'),'_embedding_tables','errors is not None and "SQLCODE: <-30>" not in str(e)','False','registry'),
 ('graph-failure-known',type_base('_status_probes'),'_status_probes','unknown.append(part)','pass # altered unknown','fail'),
 ('report-unknown-ignored',EngineStatus,'report','unknown if "graph" in self.unknown','unknown if False','report')]
 for label,cls,name,old,new,mode in cases:
  if label=='all-graphs-leak':
   # Keep a valid no-parameter all-graph SQL call; a bind mismatch is not accepted as detection.
   fn=getattr(cls,name);src=textwrap.dedent(inspect.getsource(fn));src=src.replace(" WHERE COALESCE(graph_id, '') = ?",'').replace(', [gid])',')');ns={};exec(compile(src,'<source scope mutation>','exec'),fn.__globals__,ns);replacement=ns[name]
  elif label=='graph-failure-known':
   # _status_probes has a distinct append in _count; precisely mutate its first occurrence.
   fn=getattr(cls,name);src=textwrap.dedent(inspect.getsource(fn));needle='if part:\n                unknown.append(part)';assert src.count(needle)==1;src=src.replace(needle,'if part:\n                pass');ns={};exec(compile(src,'<source unknown mutation>','exec'),fn.__globals__,ns);replacement=ns[name]
  else:replacement=mutated(cls,name,old,new)
  p=Provider({**fixture,'kg_emb_'+'4'*16:rows},routes+[('kg_emb_'+'4'*16,'edge')],reg_error='registry unavailable' if mode=='registry' else None,refused=['nodes'] if mode in ('fail','report') else []);e=engine(p)
  with patch.object(cls,name,replacement),ancillary():
   if mode=='scope':actual=e.node_count();want=sum((r.get('graph') or '')=='' for r in fixture['nodes']);results[label]=actual!=want
   else:
    s=e.status();want,errors,unknown=oracle(p)
    results[label]=(dataclasses.asdict(s.tables)!=want or set(s.unknown)!=unknown or error_tags(s)!=errors or ('graph' in unknown and 'unknown' not in next(x for x in s.report().splitlines() if x.startswith('Graph:'))))
  p.close()
 return results
def type_base(name):
 return next(cls for cls in IRISGraphEngine.__mro__ if name in cls.__dict__)
if __name__=='__main__':main()
