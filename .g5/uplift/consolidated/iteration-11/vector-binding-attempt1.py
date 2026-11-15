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
  r.statements.append((flat,args))
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
 if a['kind']=='error':return a['type']==b['type'] or {a['type'],b['type']}<={'RuntimeError','OperationalError','TypeError','ValueError'}
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
 if cells is not None:
  z.data=[dict(table=TABLE,graph='g',id=rr[0] if rr else 'bad',emb='1,0,0,0',cells=rr,labels=['keep']) for rr in cells]
 method={'primary':'kg_KNN_VEC','optimized':'_kg_KNN_VEC_python_optimized','client':'_kg_KNN_VEC_client_side'}[stage]
 origdot=np.dot;count=[0]
 def dot(*a,**kw):count[0]+=1;return origdot(*a,**kw)
 with patch.object(embedded,'_sql_statement_execute',side_effect=r.embedded_sql),patch.object(np,'dot',side_effect=dot):got=observe(lambda:getattr(e,method)(q,k=k,label_filter=label,graph='g',model_key='m'))
 want=observe(lambda:z.search(stage,q,k,label));actual_effects=effects(r,count[0]);model_effects=expected_effects(z)
 if alter and got['kind']=='rows' and got['value']:got['value'][0]=(got['value'][0][0],got['value'][0][1]+.25)
 okay=equivalent(got,want) and actual_effects==model_effects
 # Every SQL score/vector/seed statement uses the selected table and exact bound graph.
 for sql,args in r.statements:
  if 'VECTOR_COSINE' in sql or re.match(r'SELECT (?:TOP 1 )?(?:n\.)?(?:node_id, (?:n\.)?emb|emb) FROM',sql):
   if 'embedding_registry' not in sql:okay=okay and TABLE in sql and 'g' in args
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
 return out

def variant(owner,name,find,replace):
 s=textwrap.dedent(inspect.getsource(getattr(owner,name)));assert s.count(find)==1
 ns=dict(vars(sys.modules[owner.__module__]));exec(s.replace(find,replace),ns);return ns[name]
def main():
 started=time.perf_counter();cases=[];parser_cases=[];failure=None
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
  cache=cache_cases()
  baseline=case('[1,2,3]');sens={}
  fn=variant(VectorMixin,'_assert_query_width','if width == int(dimension):','if True:')
  with patch.object(IRISGraphEngine,'_assert_query_width',fn):sens['actual_width_guard_removed']=not case('[1,2,3]')['agrees']
  fn=variant(VectorMixin,'_assert_query_width','if not dimension:\n        dimension = self._catalog_width(table)','if True:\n        dimension = self._catalog_width(table)')
  with patch.object(IRISGraphEngine,'_assert_query_width',fn):sens['actual_route_precedence_removed']=not case('[1,2,3]',cat={'params':['LEN,3']})['agrees']
  fn=variant(emb.EmbeddingsMixin,'_route_cache_key','graph_id or ""','""')
  with patch.object(IRISGraphEngine,'_route_cache_key',fn):
   r=old.Registry(rows=[old.row('g1','m',TABLE),old.row('g2','m',TABLE2)]);e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();seen=[e._read_route(g,'m')[1].table_name for g in ['g1','g2']];sens['actual_graph_cache_key_removed']=seen!=[TABLE,TABLE2]
  good=case('[1,2,3,4]');sens['corrupted_final_score_rejected']=good['agrees'] and not case('[1,2,3,4]',alter=True)['agrees']
  mixed=case('[1,2,3]',None,cat={'error':True},faults=[generic,widthfault]);immediate=case('[1,2,3]',None,cat={'error':True},faults=[widthfault]);seed=case('seed',faults=[generic],k=1)
  checks=dict(parser_all=all(x['agrees'] for x in parser_cases),cache_all=all(x['agrees'] for x in cache),seed_identity_loss=seed['agrees'] and seed['got']=={'kind':'rows','value':[('seed',1.0)]},mixed_width_empty=mixed['agrees'] and mixed['got']=={'kind':'rows','value':[]} and mixed['effects']['client']==1 and mixed['effects']['kernel']==2,immediate_width_refuses=immediate['agrees'] and immediate['got']['kind']=='error' and immediate['effects']['client']==0)
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());checks={};sens={};cache=[]
 flat={};identities={}
 for rel in ['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/schema.py','iris_vector_graph/_engine/schema.py','iris_vector_graph/embedding_identity.py','iris_vector_graph/_validate.py','tests/unit/route_fakes_227.py']:
  flat[rel]=bc.sha(PIN/rel);identities[rel]=bc.sha(REPO/rel)==flat[rel]
 for f in [*HERE.glob('*.rs'),HERE/'model.json',HERE/'binding.py',HERE/'port.py',HERE.parents[1]/'tools/binding_common.py',REPO/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py']:
  flat[str(f.relative_to(REPO))]=bc.sha(f)
 for prefix in ['root-vector','root-seed','review-vector','review-seed']:
  for f in OUT.glob(prefix+'*'):
   if f.is_file():flat[str(f.relative_to(REPO))]=bc.sha(f)
 for rel in ['.g5/Verus_verification/models/temporal_restore/binding.py','.g5/uplift/consolidated/iteration-5/native-setup.json']:flat[rel]=bc.sha(REPO/rel)
 mism=[x for x in cases if not x['agrees']];sockets=CONNECT.call_count+old.CONNECT.call_count
 verdict='AGREES' if failure is None and not mism and all(checks.values()) and all(sens.values()) and all(identities.values()) and sockets==0 else 'DISAGREES'
 out=bc.write_receipt('vector_admission',Path(__file__),dict(inputs=flat,verdict=verdict,comparisons=len(cases)+len(parser_cases)+len(cache),search_comparisons=len(cases),parser_comparisons=len(parser_cases),mismatch_count=len(mism),mismatches=mism[:12],parser_misses=[x for x in parser_cases if not x['agrees']][:5],checks=checks,sensitivity=sens,cache=cache,contrasts={'seed':locals().get('seed'),'mixed':locals().get('mixed'),'immediate':locals().get('immediate')},failure=failure,current_equals_exported_pin=identities,socket_connect_calls=sockets,native_calls=0,elapsed=time.perf_counter()-started,scope='Actual pinned Python route/cache/query/readers, SQLite-scoped SQL provider with finite math cosine and explicit fault replies, raw JSON stack port vs independent stdlib oracle. NumPy client kernel actually executes; kernel numeric theorem remains provider. Native root13+seed5 and independent source21/seed6 flat-hashed supplements only; no child native/network/Git.'))
 print(json.dumps(dict(verdict=verdict,search=len(cases),parser=len(parser_cases),mismatches=len(mism),checks=checks,sensitivity=sens,failure=failure,receipt=str(out))));assert verdict=='AGREES'
if __name__=='__main__':main()
