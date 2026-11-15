"""Pinned actual Python communities decisions/cache/strict-reader/completion over raw graph ports.
No native IRIS, network, Git or product edits. SQL loners execute in in-memory SQLite.
"""
import copy,hashlib,importlib.util,inspect,itertools,json,logging,os,random,socket,sqlite3,sys,textwrap,time,traceback
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import patch
sys.dont_write_bytecode=True
NET=patch.object(socket.socket,'connect',side_effect=AssertionError('communities binding forbids network'));CONNECT=NET.start();logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];PIN=Path(os.environ.get('IVG_PIN_DIR','/Users/ziniuw/runs/ivg-consolidated-20261114/pin'));sys.path.insert(0,str(PIN))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
bc=load('communities_binding_common',HERE.parents[1]/'tools/binding_common.py');p=load('communities_raw_port',HERE/'port.py')
from iris_vector_graph._engine.algorithms import AlgorithmsMixin
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
from iris_vector_graph._collation import collation_key as order
from iris_vector_graph import _edgeless as ed,algo_cache,schema

class Cursor:
 def __init__(self,w):self.w=w;self.cur=w.db.cursor()
 def execute(self,sql,args=None):
  self.w.sql.append((sql,list(args or [])))
  if self.w.sql_fail:raise sqlite3.OperationalError('named SQL census provider failure')
  self.cur.execute(sql,args or []);return self
 def fetchall(self):return self.cur.fetchall()
 def close(self):self.cur.close()
class World:
 def __init__(self,nodes,edges,native='off',fault=None,sql_fail=False,page=20000,mutant=None):
  self.nodes=list(nodes);self.edges=list(edges);self.raw=p.coordinates(edges);self.native=native;self.fault=fault;self.sql_fail=sql_fail;self.page=page;self.mutant=mutant;self.token=1;self.cache={};self.calls=[];self.kernels=[];self.pages=[];self.sql=[];self.cache_fail=False
  self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS G");self.db.execute('CREATE TABLE G.nodes(graph_id TEXT,node_id TEXT)');self.db.execute('CREATE TABLE G.rdf_edges(graph_id TEXT,s TEXT,p TEXT,o_id TEXT,ekey INTEGER)');self.sync()
 def sync(self):
  self.db.execute('DELETE FROM G.nodes');self.db.execute('DELETE FROM G.rdf_edges');self.db.executemany('INSERT INTO G.nodes VALUES(?,?)',self.nodes);self.db.executemany('INSERT INTO G.rdf_edges VALUES(?,?,?,?,?)',self.edges)
 def cursor(self):return Cursor(self)
 def owner(self,kind,limit):
  port=p.SourcePort(self.raw,order,self.mutant)
  try:out=port.run(kind,limit);err=None
  except Exception as ex:out=None;err=type(ex).__name__
  try:want,trace=p.model(self.raw,kind,limit,order);expected_error=False
  except p.ModelRefusal as ex:want=None;trace=ex.trace;expected_error=True
  record=dict(kind=kind,limit=limit,rows=out,model=want,error=err,trace=port.trace,model_trace=trace,agrees=(err is not None)==expected_error and out==want and port.trace==trace)
  self.kernels.append(record)
  if err:raise RuntimeError('WCC did not converge')
  return json.dumps(out)
 def call(self,cls,method,*args):
  self.calls.append((cls,method,list(args)))
  if cls=='Graph.KG.AlgoCache':
   if self.cache_fail:raise RuntimeError('named cache transport fault')
   if method=='Token':return self.token
   key=tuple(args[:3])
   if method=='Lookup':
    old=self.cache.get(key)
    return 'H'+str(old[0])+'|'+old[1] if old and old[0]==self.token else 'M'+str(self.token)
   if method=='Put':self.cache[key]=(int(args[3]),args[4]);return 1
  if cls=='Graph.KG.Algorithms':
   if method=='WCCJson':return self.owner('wcc',int(args[0]) if args and args[0]!='' else None)
   if method=='CDLPJson':return self.owner('cdlp',int(args[0]) if args else 10)
  raise AssertionError((cls,method,args))
 def arno(self,cls,method,*args):
  if self.native=='summary':return json.dumps({'components':1,'largest':[]})
  return self.owner('wcc' if method=='WCCNativeJson' else 'cdlp',None if method=='WCCNativeJson' else int(args[0]))
 def classMethodValue(self,cls,method,schema_name,graph,after,page):
  assert (cls,method)==('Graph.KG.Edgeless','LonersJson');i=len(self.pages);record=dict(schema=schema_name,graph=graph,after=after,page=page);self.pages.append(record)
  if self.fault and i==self.fault[0]:
   record['fault']=self.fault[1]
   if self.fault[1]=='bad-json':return '{invalid'
   raise RuntimeError('named native census unavailable')
  # Explicit logical Source Scan port; current public workflow always supplies default graph.
  assert graph==''
  response=p.native_page(self.nodes,self.raw,after,page,order);record['reply']=response;return json.dumps(response)
 def store(self):
  s=SimpleNamespace(_algo_cache_stats={},_algo_cache_memo={},_algo_cache_off=False)
  for name in ['execute_wcc','_execute_wcc','execute_cdlp','_execute_cdlp','_cached_algorithm']:setattr(s,name,MethodType(getattr(IRISGraphStore,name),s))
  s._call_classmethod=self.call;s._arno_call=self.arno;s._native_answer=lambda algorithm,call:call() if self.native!='off' else None;s._remember_large=IRISGraphStore._remember_large;return s
 def engine(self):
  e=SimpleNamespace(_store=self.store(),_store_capabilities={'wcc':True,'cdlp':True},conn=self,_t=lambda name:'G.'+name,_iris_obj=lambda:self)
  for name in ['kg_WCC','_kg_WCC','kg_CDLP','_kg_CDLP','_loners']:setattr(e,name,MethodType(getattr(AlgorithmsMixin,name),e))
  return e

def observe(fn):
 try:return dict(kind='success',value=fn())
 except Exception as ex:return dict(kind='error',type=type(ex).__name__,message=str(ex))
def run_public(w,e,kind,limit):
 original=ed.loners
 def paged(native,schema_name,graph='',page=20000):return original(native,schema_name,graph,page=w.page)
 with patch.object(algo_cache,'enabled',return_value=True),patch.object(ed,'loners',side_effect=paged),patch.object(schema,'_call_classmethod',side_effect=lambda conn,cls,method,*args:w.call(cls,method,*args)):
  return observe(lambda:e.kg_WCC(limit) if kind=='wcc' else e.kg_CDLP(limit))
def expected(w,kind,limit):
 try:core,trace=p.model(w.raw,kind,limit,order)
 except p.ModelRefusal:return dict(kind='error')
 if w.fault and w.sql_fail:return dict(kind='error')
 loners=p.loners_sql(w.nodes,w.edges) if w.fault else p.loners_native(w.nodes,w.raw)
 return dict(kind='success',value=p.complete(core,loners,order))
def agrees(got,want):return got['kind']==want['kind'] and (got['kind']=='error' or list(got['value'].items())==list(want['value'].items()))
def case(nodes,edges,kind,limit,native='off',fault=None,sql_fail=False,page=20000,mutant=None,alter=False):
 w=World(nodes,edges,native,fault,sql_fail,page,mutant);e=w.engine();got=run_public(w,e,kind,limit);want=expected(w,kind,limit)
 if alter and got['kind']=='success' and got['value']:
  u=next(iter(got['value']));got['value'][u]='deliberately-corrupted-label'
 checked=agrees(got,want) and all(x['agrees'] for x in w.kernels)
 if got['kind']=='success' and kind=='wcc' and not fault:
  independent=p.complete(p.weak_oracle(edges,order),p.loners_sql(nodes,edges),order);checked=checked and got['value']==independent
 if fault and not sql_fail:checked=checked and len(w.sql)==1
 if fault and sql_fail:checked=checked and got['kind']=='error'
 if not fault:checked=checked and len(w.sql)==0
 result=dict(agrees=checked,input=dict(nodes=nodes,edges=edges,kind=kind,limit=limit,native=native,fault=fault,sql_fail=sql_fail,page=page),got=got,want=want,core_traces=w.kernels,page_queries=w.pages,sql=w.sql,cache_stats=dict(e._store._algo_cache_stats),calls=w.calls);w.db.close();return result

def histories():
 nodes=[('','n:a'),('','n:b'),('','n:iso')];edges=[('','n:a','R','n:b',0)];w=World(nodes,edges,page=1);a=w.engine();b=w.engine();out=[]
 for label,kind,limit in [('warm-wcc','wcc',None),('warm-cdlp','cdlp',1),('second-wcc','wcc',None),('second-cdlp','cdlp',1)]:
  got=run_public(w,a if label.startswith('warm') else b,kind,limit);want=expected(w,kind,limit);out.append(dict(name=label,agrees=agrees(got,want),got=got,stats=dict((a if label.startswith('warm') else b)._store._algo_cache_stats)))
 before=len(w.kernels);w.nodes.append(('','n:new'));w.sync()
 for kind,limit in [('wcc',None),('cdlp',1)]:
  got=run_public(w,b,kind,limit);want=expected(w,kind,limit);out.append(dict(name='isolate-add-'+kind,agrees=agrees(got,want) and got['value'].get('n:new')=='n:new' and len(w.kernels)==before,got=got,stats=dict(b._store._algo_cache_stats)))
 w.nodes=[r for r in w.nodes if r[1]!='n:new'];w.token+=1;w.sync()
 for kind,limit in [('wcc',None),('cdlp',1)]:
  got=run_public(w,b,kind,limit);out.append(dict(name='ordinary-isolate-delete-'+kind,agrees=agrees(got,expected(w,kind,limit)) and 'n:new' not in got['value'],got=got,stats=dict(b._store._algo_cache_stats)))
 w.db.close()
 # Same-token/different-raw-origin primitive witness, not a new transaction implementation.
 w=World([('','n:a'),('','n:b')],[('','n:a','R','n:b',0)]);e=w.engine();old=run_public(w,e,'wcc',None);w.edges=[];w.raw=[];w.sync();got=run_public(w,e,'wcc',None);fresh=expected(w,'wcc',None);want=dict(kind='success',value={'n:a':'n:a','n:b':'n:a'})
 out.append(dict(name='stale-core-not-repaired-by-live-loners',agrees=agrees(got,want) and got!=fresh,got=got,fresh=fresh,old=old,known_counterexample_boundary=True));w.db.close();return out

def variant(owner,name,find,replace):
 fn=getattr(owner,name);src=textwrap.dedent(inspect.getsource(fn));assert src.count(find)==1,(name,find);ns=dict(fn.__globals__);exec(src.replace(find,replace),ns);return ns[name]
def main():
 start=time.perf_counter();cases=[];failure=None;history=[];sensitivity={};effect_checks={};rng=random.Random(31212)
 try:
  graphs=[[],[('','n:a','R','n:b',0)],[('','n:c','R','n:b',0),('','n:b','R','n:a',0)],[('','n:loop','R','n:loop',0)],[('','n:x','R','n:a',0),('','n:x','S','n:z',0),('','n:x','T','n:z',0)],[('','n:x','R','n:a',0),('','n:x','R','n:z',0)],[('','n:x','R','n:a',0),('','n:x','R','n:z',0),('','n:x','R','n:z',1)]]
  for _ in range(25):graphs.append([(g,u,t,v,k) for g in ['','other'] for u,v,t,k in itertools.product(['n:a','n:b','n:c'],['n:a','n:b','n:c'],['R','S'],[0,1]) if rng.randrange(15)==0])
  for edges in graphs:
   nodes=sorted({(g,u) for g,u,t,v,k in edges}|{(g,v) for g,u,t,v,k in edges}|{('','n:iso'),('other','n:trap')})
   for kind,limit,mode in itertools.product(['wcc','cdlp'],[-1,0,1,2,3,5],['off','good','summary']):cases.append(case(nodes,edges,kind,limit,native=mode,page=2))
   for mode in ['off','good','summary']:cases.append(case(nodes,edges,'wcc',None,page=1,native=mode))
  n=[('','n:a'),('','n:b'),('','n:c'),('','n:d')]
  for fault,sql_fail in [(None,False),((1,'raise'),False),((1,'bad-json'),False),((1,'raise'),True),((0,'raise'),False)]:cases.append(case(n,[],'wcc',None,fault=fault,sql_fail=sql_fail,page=1))
  # Successful empty census and empty raw graph preserve the success/error distinction.
  cases.append(case([('','n:a'),('','n:b')],[('','n:a','R','n:b',0)],'wcc',None,page=1))
  cases.append(case([],[],'wcc',0,page=1))
  paging=cases[-7:-2];full=paging[0]['page_queries']
  effect_checks['full_final_page_extra_empty']=len(full)==5 and full[-1]['reply']=={'loners':{},'next':''}
  effect_checks['cursor_value_echoed']=all(full[i+1]['after']==full[i]['reply']['next'] for i in range(len(full)-1))
  effect_checks['partial_raise_discards_whole_native_result']=len(paging[1]['page_queries'])==2 and len(paging[1]['sql'])==1 and paging[1]['got']['value']==paging[0]['got']['value']
  effect_checks['partial_bad_json_discards_whole_native_result']=len(paging[2]['page_queries'])==2 and len(paging[2]['sql'])==1 and paging[2]['got']['value']==paging[0]['got']['value']
  effect_checks['successful_empty_avoids_sql']=cases[-2]['agrees'] and not cases[-2]['sql'] and cases[-2]['page_queries'][0]['reply']['loners']=={}
  effect_checks['empty_graph_zero_budget_success']=cases[-1]['got']=={'kind':'success','value':{}}
  native_page=p.native_page
  def overadvance(nodes,raw,after,page,key):
   answer=native_page(nodes,raw,after,page,key);ids=sorted((u for u in p.loners_native(nodes,raw) if not after or key(u)>key(after)),key=key)
   if answer['next'] and len(ids)>page:answer['next']=ids[page]
   return answer
  with patch.object(p,'native_page',overadvance):sensitivity['source_port_cursor_overadvance']=not case(n,[],'wcc',None,page=1)['agrees']
  history=histories();pair=[('','n:a','R','n:b',0)];chain=[('','n:c','R','n:b',0),('','n:b','R','n:a',0)];nodes=[('','n:a'),('','n:b'),('','n:c'),('','n:iso')]
  for mode,edges,kind,limit in [('out-only',pair,'wcc',None),('in-place',chain,'wcc',1),('guard-after-scan',pair,'wcc',1),('in-place',pair,'cdlp',2),('count-self',[('','n:a','R','n:a',0),('','n:a','R','n:b',0)],'cdlp',1),('tie-last',graphs[5],'cdlp',1),('dedup-label-votes',graphs[4],'cdlp',1)]:
   sensitivity['source_port_'+mode+'_'+kind]=not case(nodes,edges,kind,limit,mutant=mode)['agrees']
  fn=variant(AlgorithmsMixin,'kg_WCC','return complete_labels(self._kg_WCC(max_iterations), list(self._loners()))','return self._kg_WCC(max_iterations)')
  with patch.object(AlgorithmsMixin,'kg_WCC',fn):sensitivity['actual_public_live_completion_removed']=not case(nodes,pair,'wcc',None)['agrees']
  fn=variant(IRISGraphStore,'_execute_wcc','if max_iterations is None:','if True:')
  with patch.object(IRISGraphStore,'_execute_wcc',fn):sensitivity['actual_explicit_limit_native_bypass']=not case(nodes,pair,'wcc',1,native='good')['agrees']
  fn=variant(AlgorithmsMixin,'_loners','return _edgeless.loners_sql(self.conn, nodes, self._t("rdf_edges"), graph)','return {}')
  with patch.object(AlgorithmsMixin,'_loners',fn):sensitivity['actual_census_failure_silenced']=not case(nodes,pair,'wcc',None,fault=(0,'raise'))['agrees']
  fn=variant(IRISGraphStore,'_cached_algorithm','return IVGResult(columns=list(columns), rows=rows)','return IVGResult(columns=list(columns), rows=[])')
  with patch.object(IRISGraphStore,'_cached_algorithm',fn):sensitivity['actual_shared_hit_rows_lost']=not all(x['agrees'] for x in histories())
  src=textwrap.dedent(inspect.getsource(ed.complete_labels));ns=dict(ed.__dict__);exec(src.replace('out.setdefault(v, v)','out[v] = v'),ns)
  with patch.object(ed,'complete_labels',ns['complete_labels']):sensitivity['actual_existing_core_overwritten']=not all(x['agrees'] for x in histories())
  sensitivity['corrupted_observation_rejected']=case(nodes,pair,'wcc',None)['agrees'] and not case(nodes,pair,'wcc',None,alter=True)['agrees']
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc())
 flat={};identities={}
 for rel in ['iris_src/src/Graph/KG/Algorithms.cls','iris_src/src/Graph/KG/Edgeless.cls','iris_vector_graph/_engine/algorithms.py','iris_vector_graph/_edgeless.py','iris_vector_graph/stores/iris_sql_store.py','iris_vector_graph/algo_cache.py','iris_vector_graph/_collation.py','iris_vector_graph/result.py']:
  flat[rel]=bc.sha(PIN/rel);identities[rel]=bc.sha(REPO/rel)==flat[rel]
 for q in [*HERE.glob('*.rs'),HERE/'model.json',HERE/'port.py',HERE/'binding.py',HERE/'NOTES.md',HERE.parents[1]/'tools/binding_common.py']:flat[str(q.relative_to(REPO))]=bc.sha(q)
 base=REPO/'.g5/uplift/consolidated'
 for name in ['next-communities-PAIRS.md','next-communities-plan.md','next-communities-native.py','next-communities-native.json','next-communities-native.log']:q=base/'iteration-11'/name;flat[str(q.relative_to(REPO))]=bc.sha(q)
 for name in ['root-communities-census-predictions.md','root-communities-census-native.py','root-communities-census-native.json','root-communities-census-native.log','review-communities-paging-probe.py','review-communities-paging-probe.json','review-communities-paging-probe.log','communities-upstream.py','communities-upstream.json']:
  q=base/'iteration-12'/name
  if q.exists():flat[str(q.relative_to(REPO))]=bc.sha(q)
 mism=[x for x in cases if not x['agrees']];okay=failure is None and not mism and all(x['agrees'] for x in history) and all(sensitivity.values()) and all(effect_checks.values()) and all(identities.values()) and CONNECT.call_count==0
 body=dict(inputs=flat,verdict='AGREES' if okay else 'DISAGREES',comparisons=len(cases),mismatch_count=len(mism),mismatches=mism[:8],histories=history,sensitivity=sensitivity,effect_checks=effect_checks,paging_examples=paging,failure=failure,current_equals_exported_pin=identities,socket_connect_calls=CONNECT.call_count,native_executions=0,elapsed=time.perf_counter()-start,scope='Actual pinned Python engine/core dispatch/store/cache/strict reader/live completion and SQL loners over executing raw Owner/native-page ports, independent synchronous model trace and raw BFS/vote oracle. SQLite SQL executes original scoped census predicates. Native body and full collation/numeric/normalization/cache transport providers remain qualified; source mutable kernel ports are not native execution. page helper override named for small pagination tests. Known18 +root8 and independent paging5 are flat-hashed finite supplements, not supplied answer maps or private/blind evidence.')
 out=bc.write_receipt('communities',Path(__file__),body);print(json.dumps({k:body[k] for k in ['verdict','comparisons','mismatch_count','sensitivity','effect_checks','failure','elapsed']}));print(out);assert okay
if __name__=='__main__':main()
