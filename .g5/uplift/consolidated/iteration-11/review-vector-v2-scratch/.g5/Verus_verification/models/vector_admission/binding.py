"""Actual pinned route/query/readers over SQLite SQL and explicit external faults.
No native IRIS, DDL on a server, Git, network or evaluator/private files.
"""
import copy,hashlib,importlib.util,inspect,itertools,json,logging,math,os,random,re,socket,sqlite3,sys,textwrap,time,traceback
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('vector binding forbids sockets'));CONNECT=NETWORK.start();logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];OUT=REPO/'.g5/uplift/consolidated/iteration-11';PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
bc=load('vector_binding_common',HERE.parents[1]/'tools/binding_common.py');p=load('vector_model_port',HERE/'port.py');old=load('vector_inherited_fakes',REPO/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py')
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine import embeddings as emb
from iris_vector_graph._engine.vector import VectorMixin
import iris_vector_graph.embedded as embedded
import numpy as np
TABLE='kg_emb_0000000000000001';TABLE2='kg_emb_0000000000000002'
class Registry(old.Registry):
 def __init__(self,rows,**kw):
  self.db=sqlite3.connect(':memory:');self.events=[];self.data=kw.pop('data',[]);self.embedded=kw.pop('embedded','unavailable');self.cells=kw.pop('cells',None);self.score_faults=[];self.last_kernel_error=None
  super().__init__(rows=rows,**kw)
  for table in [TABLE,TABLE2,'kg_NodeEmbeddings','kg_NodeEmbeddings_optimized','kg_EdgeEmbeddings']:
   self.db.execute('CREATE TABLE '+table+'(graph_id TEXT,node_id TEXT,emb TEXT)')
  self.db.execute('CREATE TABLE rdf_labels(graph_id TEXT,s TEXT,label TEXT)')
  for x in self.data:
   self.db.execute('INSERT INTO '+x['table']+' VALUES(?,?,?)',(x['graph'],x['id'],x['emb']))
   for label in x.get('labels',[]):self.db.execute('INSERT INTO rdf_labels VALUES(?,?,?)',(x['graph'],x['id'],label))
  def cosine(a,q):
   try:
    aa=[float(x) for x in str(a).split(',')];qq=json.loads(q)
    if len(aa)!=len(qq):raise RuntimeError('SQLCODE -257 vectors of different lengths')
    den=math.sqrt(sum(x*x for x in aa)*sum(x*x for x in qq));return sum(x*y for x,y in zip(aa,qq))/den if den else None
   except Exception as ex:self.last_kernel_error=ex;raise
  self.db.create_function('VECTOR_COSINE',2,cosine)
 def cursor(self):self.opens+=1;return Cursor(self)
 def embedded_sql(self,sql,args):
  if self.embedded=='unavailable':self.events.append(('score','embedded'));raise RuntimeError('embedded unavailable')
  c=Cursor(self);c.mode='embedded';c.execute(sql,args);return c.fetchall()
class Cursor(old.Cursor):
 def __init__(self,r):super().__init__(r);self.mode='dbapi'
 def execute(self,sql,params=None):
  flat=' '.join(str(sql).split());args=list(params or []);r=self.registry
  score='VECTOR_COSINE' in flat
  vector=bool(re.match(r'SELECT (?:TOP 1 )?(?:n\.)?(?:node_id, (?:n\.)?emb|emb) FROM',flat)) and 'embedding_registry' not in flat
  if not(score or vector):return super().execute(sql,params)
  r.statements.append((flat,list(args)))
  if score:
   stage='embedded' if self.mode=='embedded' else ('primary' if flat.startswith('SELECT TOP ?') else 'dbapi');r.events.append(('score',stage))
   if stage!='embedded' and r.score_faults:
    f=r.score_faults.pop(0)
    if f:raise f
   if r.cells is not None:self._rows=copy.deepcopy(r.cells);return self
  elif flat.startswith('SELECT n.node_id, n.emb'):r.events.append(('client',))
  elif flat.startswith('SELECT TOP 1 emb'):r.events.append(('diagnostic',))
  elif flat.startswith('SELECT emb'):r.events.append(('seed',))
  elif flat.startswith('SELECT node_id, emb'):r.events.append(('ivf',))
  limit=None
  if flat.startswith('SELECT TOP ? '):limit=args.pop(0);flat=flat.replace('SELECT TOP ? ','SELECT ',1)
  else:
   m=re.match(r'SELECT TOP (\d+) ',flat)
   if m:limit=int(m[1]);flat=flat.replace(m[0],'SELECT ',1)
  flat=re.sub(r'TO_VECTOR\(\?, [A-Za-z0-9_]+\)','?',flat)
  if limit is not None:flat+=' LIMIT '+str(int(limit))
  flat=re.sub(r'Graph_KG\.', '', flat)
  r.last_kernel_error=None
  try:self._rows=list(r.db.execute(flat,args).fetchall())
  except Exception:
   if r.last_kernel_error:raise r.last_kernel_error
   raise
  return self

def observe(fn):
 try:return {'kind':'rows','value':fn()}
 except Exception as ex:return {'kind':'error','type':type(ex).__name__}
def equivalent(a,b):
 if a['kind']!=b['kind']:return False
 if a['kind']=='error':return a['type']==b['type']
 if len(a['value'])!=len(b['value']):return False
 return all(x[0]==y[0] and math.isclose(x[1],y[1],rel_tol=1e-12,abs_tol=1e-12) for x,y in zip(a['value'],b['value']))
def effects(r,kernels):
 return dict(registry=len(old.registry_reads(r)),catalog=len(old.metadata_reads(r)),score=[x[1] for x in r.events if x[0]=='score'],seed=sum(x[0]=='seed' for x in r.events),client=sum(x[0]=='client' for x in r.events),kernel=kernels,diagnostic=sum(x[0]=='diagnostic' for x in r.events))
def expected_effects(z):
 return dict(registry=sum(x[0]=='registry' for x in z.events),catalog=sum(x[1] for x in z.events if x[0]=='catalog'),score=[x[1] for x in z.events if x[0]=='score'],seed=sum(x[0]=='seed' for x in z.events),client=sum(x[0]=='client' for x in z.events),kernel=sum(x[0]=='kernel' for x in z.events),diagnostic=sum(x[0]=='diagnostic' for x in z.events))
def case(q,dim=4,stage='primary',present=True,cat=None,faults=None,embedded_mode='unavailable',cells=None,label=None,k=2,raw=None,reg_error=None,data=None,alter=False):
 data=data if data is not None else [dict(table=TABLE,graph='g',id='seed',emb='1,0,0,0',labels=['keep']),dict(table=TABLE,graph='g',id='peer',emb='1,1,0,0',labels=['keep']),dict(table=TABLE,graph='other',id='cross',emb='1,0,0,0',labels=['keep']),dict(table=TABLE2,graph='g',id='wrong_table',emb='1,0,0,0',labels=['keep'])]
 rows=[old.row(table=TABLE,dimension=dim)] if present else [];r=Registry(rows,data=data,catalog=cat,raw_rows=raw,registry_error=reg_error,embedded=embedded_mode,cells=cells);e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();r.statements.clear();r.events.clear();r.score_faults=list(faults or [])
 z=p.Port(rows=rows,raw=raw,reg_error=reg_error,cat=cat,data=data,faults=faults,embedded=embedded_mode)
 z.cells=cells
 method={'primary':'kg_KNN_VEC','optimized':'_kg_KNN_VEC_python_optimized','client':'_kg_KNN_VEC_client_side'}[stage]
 origdot=np.dot;count=[0]
 def dot(*a,**kw):count[0]+=1;return origdot(*a,**kw)
 with patch.object(embedded,'_sql_statement_execute',side_effect=r.embedded_sql),patch.object(np,'dot',side_effect=dot):got=observe(lambda:getattr(e,method)(q,k=k,label_filter=label,graph='g',model_key='m'))
 want=observe(lambda:z.search(stage,q,k,label));actual_effects=effects(r,count[0]);model_effects=expected_effects(z)
 if alter and got['kind']=='rows' and got['value']:got['value'][0]=(got['value'][0][0],got['value'][0][1]+.25)
 okay=equivalent(got,want) and actual_effects==model_effects
 expected_tables={x[3] for x in z.events if x[0]=='score'}|{x[1] for x in z.events if x[0] in ('client','seed','diagnostic')}
 # Every SQL score/vector/seed statement uses the selected table and exact bound graph.
 for sql,args in r.statements:
  if 'VECTOR_COSINE' in sql or re.match(r'SELECT (?:TOP 1 )?(?:n\.)?(?:node_id, (?:n\.)?emb|emb) FROM',sql):
   if 'embedding_registry' not in sql:okay=okay and any(t in sql for t in expected_tables) and 'g' in args
 out=dict(agrees=okay,input=dict(query=repr(q),dim=repr(dim),stage=stage,present=present,catalog=cat,faults=[str(x) for x in faults or []],embedded=embedded_mode,label=label,k=k,raw=repr(raw),cells=cells),got=got,want=want,effects=actual_effects,model_effects=model_effects,sql=r.statements)
 r.db.close();return out

def cache_cases():
 out=[];clock=[0.0]
 with patch.object(emb.time,'monotonic',side_effect=lambda:clock[0]):
  r=old.Registry(rows=[old.row(table=TABLE)]);e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();r.statements.clear();z=p.Port(rows=[old.row(table=TABLE)]);timeline=[]
  for now in [0,30,30.001]:
   clock[0]=now;z.now=now
   if now:r.registry_error=RuntimeError('backend non30');z.reg_error=RuntimeError('backend non30')
   got=observe(lambda:e._read_route('g','m'));want=observe(lambda:z.resolve('g','m'));actual=got['kind'];pred=want['kind'];timeline.append(dict(time=now,got=repr(got),want=repr(want),reads=len(old.registry_reads(r)),model_reads=sum(x[0]=='registry' for x in z.events),agrees=actual==pred and len(old.registry_reads(r))==sum(x[0]=='registry' for x in z.events)))
  out.append(dict(name='positive_ttl_and_backend_error',timeline=timeline,agrees=all(x['agrees'] for x in timeline)))
  r=old.Registry();a=old.f.engine_with(r,embedding_dimension=4);b=old.f.engine_with(r,embedding_dimension=4);r.statements.clear();first=a._read_route('g','m');n1=len(old.registry_reads(r));created=b.resolve_route('g','m',create=True,dimension=4);n2=len(old.registry_reads(r));last=a._read_route('g','m');n3=len(old.registry_reads(r))
  out.append(dict(name='absence_forecast_refuted_actual_writer',agrees=first==(True,None) and n1==1 and n2==3 and n3==4 and last[1].table_name==created.table_name,reads=[n1,n2,n3],known_nonbug=True))
 # Source calls the clock on hit/expiry and separately on cache write. Seven provider replies
 # distinguish lookup40.001 from replacement-store45; no elapsed-time rounding assumption.
 timeline=[];ticks=iter([10.,40.,40.001,45.,75.,75.001,80.]);r=old.Registry(rows=[old.row(table=TABLE)]);e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();r.statements.clear()
 with patch.object(emb.time,'monotonic',side_effect=lambda:next(ticks)):
  for i in range(5):
   e._read_route('g','m');entry=next(iter(e._route_cache_store.values()));timeline.append(dict(reads=len(old.registry_reads(r)),stored_at=entry[1]))
 out.append(dict(name='lookup_and_store_clock_replies_distinct',timeline=timeline,agrees=[x['reads'] for x in timeline]==[1,1,2,2,3] and [x['stored_at'] for x in timeline]==[10.,10.,45.,45.,80.]))

 return out

class BuildPort:
 def __init__(self,info,fault=None):self.info=info;self.fault=fault;self.calls=[]
 def classMethodValue(self,cls,method,*args):
  self.calls.append(method)
  if method==self.fault:raise RuntimeError('named '+method+' provider fault')
  return self.info if method=='Info' else 1

def ivf_cases():
 out=[]
 panels=[('no-route',False,None,[],1,500,'{}',None),('empty-ids',True,[],[],1,500,'{}',None),('no-rows',True,None,[],1,500,'{}',None),('all-none',True,None,[None],1,500,'{}',None),('one-vector',True,None,['1,0,0,0'],1,500,'{"dim":4}',None),('malformed-info',True,None,['1,0,0,0'],1,500,'not-json',None),('None-info',True,None,['1,0,0,0'],1,500,None,None),('null-info-valid',True,None,['1,0,0,0'],1,500,'null',None),('coercible-nlist-not-rewritten',True,None,['1,0,0,0'],'1',500,'{}',None),('coercible-build-batch-not-rewritten',True,None,['1,0,0,0'],1,'500','{}',None),('Build-fault',True,None,['1,0,0,0'],1,500,'{}','Build'),('Info-fault',True,None,['1,0,0,0'],1,500,'{}','Info')]
 for name,present,ids,raw,nlist,batch,info,fault in panels:
  data=[dict(table=TABLE,graph='g',id='n'+str(i),emb=v,labels=[]) for i,v in enumerate(raw)]
  r=Registry([old.row(table=TABLE)] if present else [],data=data);e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();r.statements.clear();r.events.clear();native=BuildPort(info,fault);e._iris_obj=lambda:native;index='binding_'+name.replace('-','_');before=(dict(e._index_registry),dict(e._index_graph_scopes))
  got=observe(lambda:e.ivf_build(index,nlist=nlist,build_batch_size=batch,node_ids=ids,graph='g',model_key='m'));after=(dict(e._index_registry),dict(e._index_graph_scopes))
  # Independent admission/effect fold over raw args/rows; kernel/clustering is an admitted provider.
  expected=[];error=True;published=False
  if present and ids!=[] and raw:
   vectors=[v for v in raw if v is not None]
   widths=[p.width('['+v+']') for v in vectors]
   rectangular=bool(vectors) and all(w is not None and w==widths[0] for w in widths)
   if rectangular and isinstance(nlist,int):
    expected=['Build']
    if fault!='Build' and isinstance(batch,int):
     expected+=['AddBatch']*math.ceil(len(vectors)/batch)+['FinalizeIndex','Info']
     if fault!='Info' and isinstance(info,str) and p.parse(info) is not None:error=False;published=True
  okay=native.calls==expected and ((got['kind']=='error')==error) and ((after!=before)==published)
  if published:okay=okay and e._index_registry[index]=='ivf' and e._index_graph_scopes[index]=='g'
  if not present:okay=okay and not any(x[0]=='ivf' for x in r.events)
  if name=='malformed-info':okay=okay and got['type']=='JSONDecodeError' and after==before
  out.append(dict(name=name,raw_vectors=raw,nlist=repr(nlist),build_batch=repr(batch),info=repr(info),got=got,expected_methods=expected,actual_methods=native.calls,published=published,agrees=okay,sql=r.statements));r.db.close()
 return out

def variant(owner,name,find,replace):
 s=textwrap.dedent(inspect.getsource(getattr(owner,name)));assert s.count(find)==1
 ns=dict(getattr(owner,name).__globals__);exec(s.replace(find,replace),ns);return ns[name]
def main():
 started=time.perf_counter();cases=[];parser_cases=[];constructor=[];failure=None
 try:
  corpus=['[]','[1,2,3]',' [1,2,3,4] ','[[1,2],{"k":true}]','[true,false,null,"x"]',r'["a,b","quote\""]','[NaN,Infinity,-Infinity]','[1,-2.5e+2,3E-4]','[1,]','[.1]','[01]','[1]junk','["\\u00a0",{}]','\u2003[1,2]\u2003']
  rng=random.Random(21111)
  values=[None,True,False,1,-2,.25,'a,b','[,]','quote"',[],{},[1,2],{'k':[1,None]}]
  for _ in range(240):corpus.append(json.dumps([rng.choice(values) for _ in range(rng.randrange(7))]))
  for q in corpus:
   try:x=json.loads(q.strip());w=len(x) if isinstance(x,list) else None
   except (ValueError,TypeError):w=None
   parser_cases.append(dict(raw=q,model=p.width(q),stdlib=w,agrees=p.width(q)==w))
  for q,dim,stage,mode in itertools.product(corpus[:14],[None,0,3,4],['primary','optimized','client'],['unavailable','success']):cases.append(case(q,dim,stage,embedded_mode=mode))
  for q,stage,present in itertools.product(['[1,2,3]','[]','[1,2,3,4]','seed'],['primary','optimized','client'],[False,True]):cases.append(case(q,stage=stage,present=present))
  cats=[{}, {'params':['TYPE,VECTOR,LEN,4']},{'params':['LEN\x01\x034']},{'info':[('VECTOR(DOUBLE,4)',None,None)]},{'info':[('VARCHAR(4000)',None,None)]},{'error':True}]
  for c,q,stage in itertools.product(cats,['[1,2,3]','[1,2,3,4]'],['primary','optimized','client']):cases.append(case(q,None,stage,cat=c))
  for dim,stage in itertools.product([None,'',0,False,True,'4','bad'],['primary','optimized','client']):cases.append(case('[1,2,3,4]',dim,stage))
  generic=RuntimeError('first score generic unavailable');widthfault=RuntimeError('SQLCODE -257 vectors of different lengths')
  for q,stage,fs in itertools.product(['[1,2,3]','[1,2,3,4]','seed'],['primary','optimized'],[[generic],[widthfault],[generic,widthfault]]):cases.append(case(q,None,stage,cat={'error':True},faults=fs))
  for cells,stage,mode in itertools.product([[(None,'0.5'),('keep','0.75')],[('n',None)],[('n',True)],[('n',1)],[('n','0.75')],[('n',1,'extra')]],['primary','optimized'],['success','unavailable']):cases.append(case('[1,2,3,4]',cells=cells,stage=stage,embedded_mode=mode))
  for raw in [[('short',)],[(None,4,'DOUBLE',None,None)],[(TABLE,4,7,None,None)]]:cases.append(case('[1,2,3]',raw=raw))
  for label in [None,'','keep','missing']:cases.append(case('[1,2,3,4]',stage='client',label=label))
  cache=cache_cases();ivf=ivf_cases()
  original=dict(registry='Graph_KG.embedding_registry',graph='g',model='m',kind='node',ttl=30,now=0,write_at=1)
  raw_requests=[original,{**original,'registry':'other','graph':'other','model':'other','kind':'edge','ttl':0,'now':40,'write_at':45},{**original,'registry':'other2','graph':'other2','model':None,'kind':'edge','ttl':-1,'now':75,'write_at':80}]
  constructor=[]
  for i,stage in enumerate(['primary','optimized','client']):
   got=p.phase_request(raw_requests,stage);wanted={**original,'now':raw_requests[i]['now'],'write_at':raw_requests[i]['write_at']}
   constructor.append(dict(stage=stage,raw=raw_requests[i],derived=got,expected_original_engine= wanted,agrees=got==wanted))

  baseline=case('[1,2,3]');sens={}
  fn=variant(VectorMixin,'_assert_query_width','if width == int(dimension):','if True:')
  with patch.object(IRISGraphEngine,'_assert_query_width',fn):sens['actual_width_guard_removed']=not case('[1,2,3]')['agrees']
  fn=variant(VectorMixin,'_assert_query_width','if not dimension:\n        dimension = self._catalog_width(table)','if True:\n        dimension = self._catalog_width(table)')
  with patch.object(IRISGraphEngine,'_assert_query_width',fn):sens['actual_route_precedence_removed']=not case('[1,2,3]',cat={'params':['LEN,3']})['agrees']
  fn=variant(emb.EmbeddingsMixin,'_route_cache_key','graph_id or ""','""')
  with patch.object(IRISGraphEngine,'_route_cache_key',fn):
   r=old.Registry(rows=[old.row('g1','m',TABLE),old.row('g2','m',TABLE2)]);e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();seen=[e._read_route(g,'m')[1].table_name for g in ['g1','g2']];sens['actual_graph_cache_key_removed']=seen!=[TABLE,TABLE2]

  fn=variant(VectorMixin,'_kg_KNN_VEC_python_optimized','for row in rs if row[0] is not None','for row in rs if True')
  with patch.object(IRISGraphEngine,'_kg_KNN_VEC_python_optimized',fn):sens['actual_embedded_None_filter_removed']=not case('[1,2,3,4]',stage='optimized',embedded_mode='success',cells=[(None,'0.5'),('keep','0.75')])['agrees']
  with patch.dict(IRISGraphEngine.kg_KNN_VEC.__globals__,{'_is_width_mismatch':lambda error:False}):sens['actual_primary_257_classifier_removed']=not case('[1,2,3]',None,cat={'error':True},faults=[widthfault])['agrees']
  fn=variant(VectorMixin,'kg_KNN_VEC','elif exclude_id:','elif False:')
  with patch.object(IRISGraphEngine,'kg_KNN_VEC',fn):sens['actual_primary_seed_exclusion_removed']=not case('seed',k=1)['agrees']
  fn=variant(VectorMixin,'ivf_build','result = _json.loads(str(info))','result = {}')
  with patch.object(IRISGraphEngine,'ivf_build',fn):sens['actual_IVF_Info_parser_removed']=not all(x['agrees'] for x in ivf_cases())
  with patch.object(p,'width',side_effect=lambda raw:0):sens['model_port_raw_width_zeroed']=not case('[1,2,3,4]')['agrees']
  good=case('[1,2,3,4]');sens['corrupted_final_score_rejected']=good['agrees'] and not case('[1,2,3,4]',alter=True)['agrees']
  mixed=case('[1,2,3]',None,cat={'error':True},faults=[generic,widthfault]);immediate=case('[1,2,3]',None,cat={'error':True},faults=[widthfault]);seed=case('seed',faults=[generic],k=1)
  checks=dict(fixed_phase_engine_constructor=all(x['agrees'] for x in constructor),ivf_all=all(x['agrees'] for x in ivf),parser_all=all(x['agrees'] for x in parser_cases),cache_all=all(x['agrees'] for x in cache),seed_identity_loss=seed['agrees'] and seed['got']=={'kind':'rows','value':[('seed',1.0)]},mixed_width_empty=mixed['agrees'] and mixed['got']=={'kind':'rows','value':[]} and mixed['effects']['client']==1 and mixed['effects']['kernel']==2,immediate_width_refuses=immediate['agrees'] and immediate['got']['kind']=='error' and immediate['effects']['client']==0)
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());checks={};sens={};cache=[];ivf=[];constructor=[]
 flat={};identities={}
 for rel in ['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/schema.py','iris_vector_graph/_engine/schema.py','iris_vector_graph/embedding_identity.py','iris_vector_graph/_validate.py','tests/unit/route_fakes_227.py']:
  flat[rel]=bc.sha(PIN/rel);identities[rel]=bc.sha(REPO/rel)==flat[rel]
 for f in [*HERE.glob('*.rs'),HERE/'model.json',HERE/'binding.py',HERE/'port.py',HERE.parents[1]/'tools/binding_common.py',REPO/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py']:
  flat[str(f.relative_to(REPO))]=bc.sha(f)
 for name in ['root-vector-native.py','root-vector-native.json','root-vector-native.log','root-vector-predictions.md','root-seed-native.py','root-seed-native.json','root-seed-native.log','root-seed-predictions.md','review-vector-expectations.md','review-vector-fresh.py','review-vector-fresh.json','review-vector-fresh-audit.json','review-seed-predictions.md','review-seed-probe.py','review-seed-probe.json','review-seed-intent.md','review-seed-audit.py','review-seed-audit.json']:
  f=OUT/name
  if f.exists():flat[str(f.relative_to(REPO))]=bc.sha(f)
 for rel in ['.g5/Verus_verification/models/temporal_restore/binding.py','.g5/uplift/consolidated/iteration-5/native-setup.json']:flat[rel]=bc.sha(REPO/rel)
 mism=[x for x in cases if not x['agrees']];sockets=CONNECT.call_count+old.CONNECT.call_count
 verdict='AGREES' if failure is None and not mism and all(checks.values()) and all(sens.values()) and all(identities.values()) and sockets==0 else 'DISAGREES'
 out=bc.write_receipt('vector_admission',Path(__file__),dict(inputs=flat,verdict=verdict,comparisons=len(cases)+len(parser_cases)+len(cache)+len(ivf),search_comparisons=len(cases),parser_comparisons=len(parser_cases),mismatch_count=len(mism),mismatches=mism[:12],parser_misses=[x for x in parser_cases if not x['agrees']][:5],checks=checks,sensitivity=sens,cache=cache,ivf=ivf,constructor_projections=constructor,contrasts={'seed':locals().get('seed'),'mixed':locals().get('mixed'),'immediate':locals().get('immediate')},failure=failure,current_equals_exported_pin=identities,socket_connect_calls=sockets,native_calls=0,elapsed=time.perf_counter()-started,scope='Actual pinned Python route/cache/query/readers, SQLite-scoped SQL provider with finite math cosine and explicit fault replies, raw JSON stack port vs independent stdlib oracle. NumPy client kernel actually executes; kernel numeric theorem remains provider. Native root13+seed5 and independent source21/seed6 flat-hashed supplements only; no child native/network/Git.'))
 print(json.dumps(dict(verdict=verdict,search=len(cases),parser=len(parser_cases),mismatches=len(mism),checks=checks,sensitivity=sens,failure=failure,receipt=str(out))));assert verdict=='AGREES'
if __name__=='__main__':main()
